from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import red
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import qrcode
import os
import json
from datetime import datetime
import textwrap
import uuid
import re
import textwrap
import img2pdf
from flask import Flask, render_template, request, redirect, url_for, send_file
from PIL import Image, ImageDraw, ImageFont
import locale
import textwrap
from flask import abort
from io import BytesIO
from reportlab.lib.utils import ImageReader
from dateutil.relativedelta import relativedelta
import random




global usuarios






chave_qr = str(uuid.uuid4())

app = Flask(__name__)
app.secret_key = 'pandoox'

ocrb_path = os.path.join(app.root_path, 'static', 'fonts', 'OCR-B.ttf')
pdfmetrics.registerFont(TTFont('OCRB', ocrb_path))



def carregar_usuarios():
    with open('usuarios.json', 'r') as f:
        return json.load(f)

def salvar_usuarios(usuarios):
    with open('usuarios.json', 'w') as f:
        json.dump(usuarios, f, indent=2)


def salvar_cnh_do_usuario(usuario, nova_cnh):
    caminho = f'dados/{usuario}_cnhs.json'
    os.makedirs('dados', exist_ok=True)

    try:
        with open(caminho, 'r') as f:
            cnhs = json.load(f)
    except FileNotFoundError:
        cnhs = []

    # Evita duplicatas pelo número de registro
    for cnh in cnhs:
        if cnh['id'] == nova_cnh['id']:
            return False  # Já existe

    cnhs.append(nova_cnh)

    with open(caminho, 'w') as f:
        json.dump(cnhs, f, indent=2)

    return True
################################################


@app.route('/salvar_cnh', methods=['POST'])
def salvar_cnh():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    dados = request.form.to_dict()

 
    

    nova_cnh = {
        'id': dados['numero_registro'],
        'nome': dados['nome_completo'],
        'uf': dados['local_uf'],
        'data': datetime.now().strftime('%d/%m/%Y'),
        'arquivo': 'cnh_final.pdf'
    }

    sucesso = salvar_cnh_do_usuario(usuario, nova_cnh)

    if sucesso:
        flash("CNH salva com sucesso!", "sucesso")
    else:
        flash("Essa CNH já foi salva anteriormente.", "erro")

    return redirect('/cnhs_salvas')

############################################################################

def carregar_cnhs_do_usuario(usuario):
    caminho = f'dados/{usuario}_cnhs.json'
    try:
        with open(caminho, 'r') as f:
            cnhs = json.load(f)
    except FileNotFoundError:
        return []

    cnhs_validas = []
    for cnh in cnhs:
        id_ok = cnh.get('id') and len(cnh['id'].strip()) >= 5
        nome_ok = cnh.get('nome') and len(cnh['nome'].strip()) >= 3
        arquivo_ok = cnh.get('arquivo')

        caminho_pdf = os.path.join(app.root_path, 'static', 'cnhs', usuario, arquivo_ok or '')
        existe_pdf = os.path.exists(caminho_pdf)

        if id_ok and nome_ok and existe_pdf:
            cnhs_validas.append(cnh)

    with open(caminho, 'w') as f:
        json.dump(cnhs_validas, f, indent=2)

    return cnhs_validas

######################################################################################

@app.route('/login', methods=['GET', 'POST'])
def login():
    usuarios = carregar_usuarios()

    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']

        if usuario in usuarios and usuarios[usuario]['senha'] == senha:
            session['usuario'] = usuario
            tipo = usuarios[usuario]['tipo']

            # ✅ Redireciona conforme o tipo
            if tipo == 'admin':
                return redirect('/admin')
            elif tipo == 'gerente':
                return redirect('/painel_gerente')
            elif tipo == 'revendedor':
                return redirect('/painel_revendedor')
            else:
                return redirect('/dashboard')
        else:
            erro = "Usuário ou senha incorretos"
            return render_template('login.html', erro=erro)

    # GET → não envia erro
    return render_template('login.html')

##############################################################################################################################

@app.route('/painel_revendedor', methods=['GET', 'POST'])
def painel_revendedor():
    if 'usuario' not in session:
        return redirect('/login')

    usuarios = carregar_usuarios()
    revendedor = session['usuario']

    if usuarios[revendedor]['tipo'] != 'revendedor':
        return redirect('/login')

    if request.method == 'POST':
        # Criar cliente
        if 'usuario' in request.form and 'senha' in request.form and 'creditos' in request.form:
            novo = request.form['usuario']
            senha = request.form['senha']
            try:
                creditos = int(request.form['creditos'])
            except ValueError:
                flash("Valor de crédito inválido.", "erro")
                return redirect('/painel_revendedor')

            if creditos <= 0:
                flash("O valor de crédito deve ser maior que zero.", "erro")
                return redirect('/painel_revendedor')

            if novo not in usuarios:
                saldo_atual = usuarios[revendedor]['creditos']
                if saldo_atual >= creditos:
                    usuarios[revendedor]['creditos'] -= creditos
                    usuarios[novo] = {
                        "senha": senha,
                        "tipo": "usuario",
                        "creditos": creditos,
                        "revendedor": revendedor,
                        "criado_por": revendedor
                    }
                    salvar_usuarios(usuarios)
                    flash(f"Cliente {novo} criado com R$ {creditos}.", "sucesso")
                else:
                    flash(
                        f"Você não tem saldo suficiente para criar esse cliente. "
                        f"Tente recarregar sua conta ou reduzir o valor. "
                        f"Saldo atual: R$ {saldo_atual}",
                        "erro"
                    )

        # Transferir saldo
        if 'destino' in request.form and 'valor' in request.form:
            destino = request.form['destino']
            try:
                valor = int(request.form['valor'])
            except ValueError:
                flash("Valor de transferência inválido.", "erro")
                return redirect('/painel_revendedor')

            if valor <= 0:
                flash("O valor da transferência deve ser maior que zero.", "erro")
                return redirect('/painel_revendedor')

            if destino not in usuarios:
                flash(f"O cliente '{destino}' não foi encontrado.", "erro")
                return redirect('/painel_revendedor')

            if usuarios[destino]['tipo'] != 'usuario':
                flash(f"O destino '{destino}' não é um cliente válido.", "erro")
                return redirect('/painel_revendedor')

            # Agora sim, pode transferir
            if usuarios[revendedor]['creditos'] >= valor:
                usuarios[revendedor]['creditos'] -= valor
                usuarios[destino]['creditos'] += valor
                salvar_usuarios(usuarios)
                flash(f"Transferência de R$ {valor} para {destino} realizada.", "sucesso")
            else:
                flash(
                    f"Você não tem saldo suficiente para transferir R$ {valor}. "
                    f"Saldo atual: R$ {usuarios[revendedor]['creditos']}.",
                    "erro"
                )


    clientes = {
        u: d for u, d in usuarios.items()
        if d.get('tipo') == 'usuario' and d.get('revendedor') == revendedor
    }

    return render_template(
        'painel_revendedor.html',
        revendedor=revendedor,
        clientes=clientes,
        creditos=usuarios[revendedor]['creditos']
    )

############################################################################################################

@app.route('/painel_gerente', methods=['GET', 'POST'])
def painel_gerente():
    if 'usuario' not in session:
        return redirect('/login')

    usuarios = carregar_usuarios()
    gerente = session['usuario']

    if usuarios[gerente]['tipo'] != 'gerente':
        return redirect('/login')

    if request.method == 'POST':
        # Criar revendedor
        if 'usuario' in request.form and 'senha' in request.form and 'creditos' in request.form:
            novo = request.form['usuario']
            senha = request.form['senha']
            try:
                creditos = int(request.form['creditos'])
            except ValueError:
                flash("Valor de crédito inválido.", "erro")
                return redirect('/painel_gerente')

            if creditos <= 0:
                flash("O valor de crédito deve ser maior que zero.", "erro")
                return redirect('/painel_gerente')

            if novo not in usuarios:
                saldo_atual = usuarios[gerente]['creditos']
                if saldo_atual >= creditos:
                    usuarios[gerente]['creditos'] -= creditos
                    usuarios[novo] = {
                        "senha": senha,
                        "tipo": "revendedor",
                        "creditos": creditos,
                        "gerente": gerente,
                        "criado_por": gerente
                    }
                    salvar_usuarios(usuarios)
                    flash(f"Revendedor {novo} criado com R$ {creditos}.", "sucesso")
                else:
                    flash(
                        f"Você não tem saldo suficiente para criar esse revendedor. "
                        f"Tente recarregar sua conta ou reduzir o valor. "
                        f"Saldo atual: R$ {saldo_atual}",
                        "erro"
                    )

        # Transferir saldo
        if 'destino' in request.form and 'valor' in request.form:
            destino = request.form['destino']
            try:
                valor = int(request.form['valor'])
            except ValueError:
                flash("Valor de transferência inválido.", "erro")
                return redirect('/painel_gerente')

            if valor <= 0:
                flash("O valor da transferência deve ser maior que zero.", "erro")
                return redirect('/painel_gerente')

            if destino not in usuarios:
                flash(f"O revendedor '{destino}' não foi encontrado.", "erro")
                return redirect('/painel_gerente')

            if usuarios[destino]['tipo'] != 'revendedor':
                flash(f"O destino '{destino}' não é um revendedor válido.", "erro")
                return redirect('/painel_gerente')

            saldo_atual = usuarios[gerente]['creditos']
            if saldo_atual >= valor:
                usuarios[gerente]['creditos'] -= valor
                usuarios[destino]['creditos'] += valor
                salvar_usuarios(usuarios)
                flash(f"Transferência de R$ {valor} para {destino} realizada.", "sucesso")
            else:
                flash(
                    f"Você não tem saldo suficiente para transferir R$ {valor}. "
                    f"Saldo atual: R$ {saldo_atual}. Tente recarregar sua conta.",
                    "erro"
                )

    revendedores = {
        u: d for u, d in usuarios.items()
        if d.get('tipo') == 'revendedor' and d.get('gerente') == gerente
    }

    return render_template(
        'painel_gerente.html',
        gerente=gerente,
        revendedores=revendedores,
        creditos=usuarios[gerente]['creditos']
    )

#####################################################################################################################

@app.route('/admin', methods=['GET', 'POST'])
def painel_admin():
    usuarios = carregar_usuarios()

    if 'usuario' not in session or usuarios[session['usuario']]['tipo'] != 'admin':
        return redirect('/login')

    if request.method == 'POST':
        # ✅ Criação de novo usuário
        if 'usuario' in request.form and 'senha' in request.form and 'creditos' in request.form and 'tipo' in request.form:
            novo_usuario = request.form['usuario']
            senha = request.form['senha']
            creditos = int(request.form['creditos'])
            novo_tipo = request.form['tipo']
            tipo_logado = usuarios[session['usuario']]['tipo']

            # 🔒 Permissão: admin pode criar qualquer tipo
            if tipo_logado == 'admin':
                if novo_usuario not in usuarios:
                    usuarios[novo_usuario] = {
                        "senha": senha,
                        "tipo": novo_tipo,
                        "creditos": creditos,
                        "criado_por": session['usuario'],
                            "historico_creditos": [
                                {
                                    "valor": creditos,
                                    "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                            ]
                    }
                    salvar_usuarios(usuarios)

        # ✅ Atualizar créditos
        elif 'editar_usuario' in request.form and 'novo_credito' in request.form:
            nome = request.form['editar_usuario']
            novo_credito = int(request.form['novo_credito'])
            if nome in usuarios:
                saldo_antigo = usuarios[nome].get('creditos', 0)
                valor_adicionado = novo_credito - saldo_antigo
            
                usuarios[nome]['creditos'] = novo_credito
            
                if valor_adicionado > 0:
                    if 'historico_creditos' not in usuarios[nome]:
                        usuarios[nome]['historico_creditos'] = []
            
                    usuarios[nome]['historico_creditos'].append({
                        "valor": valor_adicionado,
                        "data": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
            
                salvar_usuarios(usuarios)
            

        # ✅ Excluir usuário
        elif 'excluir_usuario' in request.form:
            nome = request.form['excluir_usuario']
            if nome in usuarios:
                del usuarios[nome]
                salvar_usuarios(usuarios)

        # ✅ Trocar senha
        elif 'usuario_troca' in request.form and 'nova_senha' in request.form:
            nome = request.form['usuario_troca']
            nova_senha = request.form['nova_senha']
            if nome in usuarios:
                usuarios[nome]['senha'] = nova_senha
                salvar_usuarios(usuarios)

        return redirect('/admin')

    return render_template('painel_admin.html', usuarios=usuarios, tipo_logado=usuarios[session['usuario']]['tipo'])




#######################################################################################


@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()
    dados = usuarios.get(usuario, {})  # ← adiciona o objeto completo do usuário

    creditos = dados.get('creditos', 0)
    cnhs_salvas = carregar_cnhs_do_usuario(usuario)

    return render_template(
        'dashboard.html',
        usuario=usuario,
        dados=dados,
        creditos=creditos,
        cnhs_salvas=cnhs_salvas,
        usuarios=usuarios  # ✅ ESSENCIAL para o HTML funcionar
    )



#######################################################################################################

@app.route('/cnhs_salvas')
def cnhs_salvas():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    cnhs = carregar_cnhs_do_usuario(usuario)
    return render_template('cnhs_salvas.html', cnhs_salvas=cnhs)

###############################################################################################################

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

######################################################################################################################



pdfmetrics.registerFont(TTFont('AmrysSemibold', os.path.join(app.root_path, 'static', 'fonts', 'Amrys-Semibold.ttf')))
pdfmetrics.registerFont(TTFont('AmrysRegular', os.path.join(app.root_path, 'static', 'fonts', 'Amrys-Regular.ttf')))
pdfmetrics.registerFont(
    TTFont('NimbusMonoBold', os.path.join(app.root_path, 'static', 'fonts', 'NimbusMonoL-Bold.ttf'))
)

#################################################################################################################################

@app.route('/verificar_credito', methods=['POST'])
def verificar_credito():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()

    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'  # proteção extra

    custo_cnh = 40 if tipo == 'usuario' else 20
    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo_cnh:
        flash(f"Você não possui créditos suficientes para gerar CNH. Cada CNH custa R${custo_cnh}. Seu saldo: R${saldo}.", "erro")
        return redirect('/dashboard')

    return redirect('/formulario')

##################################################################################################################################################



@app.route('/')
def index():
    return render_template('login.html')

########################################################################################################################################################

@app.route('/formulario')
def formulario():
    if 'usuario' not in session:
        return redirect('/login')

    chave = request.args.get('chave')
    dados_precarregados = {}

    if chave:
        try:
            with open('registros_qr.json', 'r', encoding='utf-8') as f:
                registros = json.load(f)
            dados_precarregados = registros.get(chave, {})
        except Exception as e:
            print(f"❌ Erro ao carregar dados: {e}")

    return render_template('formulario.html', dados=dados_precarregados)



###############################################################################################################################################################

@app.route('/baixar/<usuario>/<nome_arquivo>')
def baixar_pdf_usuario(usuario, nome_arquivo):
    pasta = os.path.join(app.root_path, 'static', 'cnhs', usuario)
    return send_from_directory(pasta, nome_arquivo, as_attachment=True)

##################################################################################################################################################################


@app.route('/excluir_cnh/<id>', methods=['POST'])
def excluir_cnh(id):
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    caminho_json = f'dados/{usuario}_cnhs.json'

    try:
        with open(caminho_json, 'r') as f:
            cnhs = json.load(f)
    except FileNotFoundError:
        cnhs = []

    # Filtra CNHs removendo a que tem o ID correspondente
    nova_lista = []
    for cnh in cnhs:
        if cnh['id'] != id:
            nova_lista.append(cnh)
        else:
            # Apaga o arquivo PDF
            caminho_pdf = os.path.join(app.root_path, 'static', 'cnhs', usuario, cnh['arquivo'])

            if os.path.exists(caminho_pdf):
                os.remove(caminho_pdf)

    # Salva nova lista
    with open(caminho_json, 'w') as f:
        json.dump(nova_lista, f, indent=2)

    flash("CNH excluída com sucesso!", "sucesso")
    return redirect('/cnhs_salvas')


###########################################################################################################################################################
def formatar_data(data_iso):
    if data_iso:
        try:
            return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return data_iso
    return ""




@app.route('/gerar_cnh', methods=['POST'])
def gerar_cnh():
    if 'usuario' not in session:
        return redirect('/login')
    
    usuario = session['usuario']
    usuarios = carregar_usuarios()

    # 🔹 Define o custo da CNH conforme o tipo de usuário
    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'
    custo_cnh = 40 if tipo == 'usuario' else 20




    print(f"Tipo do usuário: {tipo}")


    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo_cnh:
        return f"Créditos insuficientes. Cada CNH custa R${custo_cnh}. Seu saldo: R${saldo}"

    # Reduz 1 crédito
    usuarios[usuario]['creditos'] -= custo_cnh
    salvar_usuarios(usuarios)

    dados = request.form.to_dict()

    # Criar pasta do usuário
    pasta_usuario = os.path.join(app.root_path, 'static', 'cnhs', usuario)
    os.makedirs(pasta_usuario, exist_ok=True)

    cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
    nome_arquivo = f"cnh_{cpf}.pdf"
    caminho_pdf = os.path.join(pasta_usuario, nome_arquivo)

    # ✅ Cria o PDF definitivo
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(100, 800, f"Nome: {dados.get('nome_completo', '')}")
    c.drawString(100, 780, f"Número de Registro: {dados.get('numero_registro', '')}")
    c.drawString(100, 760, f"UF: {dados.get('local_uf', '')}")
    c.drawString(100, 740, f"Data de Emissão: {datetime.now().strftime('%d/%m/%Y')}")

    # 🟩 Bloco das observações

    # Captura as observações corretamente, mesmo que venham como string com "|"
    obs_raw = request.form.get('observacoes', '').strip()
    obs_list = request.form.getlist('observacoes[]')

    texto_observacoes = " | ".join([obs_raw] + obs_list).strip()
    observacoes = [x.strip() for x in re.split(r'\s*\|\s*', texto_observacoes) if x.strip()]

    y = 700  # posição inicial (ajuste conforme seu layout)
    c.setFont("Helvetica", 10)
    for obs in observacoes:
        linhas = textwrap.wrap(obs.upper(), width=80)
        for linha in linhas:
            c.drawString(100, y, linha)
            y -= 14
        y -= 6

    # ✅ Apenas este save
    c.save()

    nova_cnh = {
        'id': dados.get('numero_registro', ''),
        'nome': dados.get('nome_completo', ''),
        'uf': dados.get('local_uf', ''),
        'data': datetime.now().strftime('%d/%m/%Y'),
        'arquivo': nome_arquivo
    }

    if nova_cnh['id'] and nova_cnh['nome'] and nova_cnh['uf'] and nome_arquivo:
        salvar_cnh_do_usuario(usuario, nova_cnh)


 

    # 🔹 Gerar chave única
    chave_qr = str(uuid.uuid4())


    nome_foto = f"{cpf}_3x4.png"

    # 🔹 Preparar dados para resultado.html
    dados_resultado = {
        "nome": dados.get("nome_completo"),
        "cpf": dados.get("cpf"),
        "rg": f"{dados.get('doc_identidade')} / {dados.get('orgao_emissor')}",
        "data_nascimento": formatar_data(dados.get("data_nascimento")),
        "registro_cnh": dados.get("numero_registro"),
        "categoria": dados.get("categoria_habilitacao"),
        "renach": dados.get("numero_renach"),
        "espelho": dados.get("numero_espelho"),
        "cidade_uf": f"{dados.get('local_municipio')} / {dados.get('local_uf')}",
        "data_emissao": formatar_data(dados.get("data_emissao")),
        "foto": f"/static/fotos/{nome_foto}" if nome_foto else ""




    }

    # 🔹 Salvar no registros_qr.json
    try:
        with open('registros_qr.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        registros = {}

    # Verifica se já existe um registro com o mesmo CPF
    cpf_atual = dados_resultado.get("cpf")
    chave_existente = None

    for chave, registro in registros.items():
        if registro.get("cpf") == cpf_atual:
            chave_existente = chave
            break


   # # ✅ Controle de edição por CPF
   # if chave_existente:
   #     edicoes = registros[chave_existente].get("edicoes", 0)
   #     if edicoes >= 1:
   #         return render_template('formulario.html', dados=dados_resultado, erro="Este CPF já foi editado uma vez. Não é possível editar novamente.")
#
   #     else:
   #         dados_resultado["edicoes"] = edicoes + 1
   #         chave_qr = chave_existente
   # else:
   #     dados_resultado["edicoes"] = 0
   #     chave_qr = str(uuid.uuid4())

    # Atualiza ou cria o registro
    registros[chave_qr] = dados_resultado

    with open('registros_qr.json', 'w', encoding='utf-8') as f:
        json.dump(registros, f, indent=4, ensure_ascii=False)




    # Usa a chave existente ou gera uma nova
    if chave_existente:
        chave_qr = chave_existente
    else:
        chave_qr = str(uuid.uuid4())

    # Atualiza ou cria o registro
    registros[chave_qr] = dados_resultado

    with open('registros_qr.json', 'w', encoding='utf-8') as f:
        json.dump(registros, f, indent=4, ensure_ascii=False)



        
    # 🔹 Gerar QR com link de consulta
    #url_qr = f"http://192.168.0.101:5000/consulta/{chave_qr}"

    url_qr = f" https://pierre-photoactinic-zoe.ngrok-free.dev/consulta/{chave_qr}"
    
    #url_qr = f"https://senatran-consulta-carteira-digital-transito.gt.tc/visualizar_cnh.php?id={chave_qr}"



    img = qrcode.make(url_qr)
    qr_path = os.path.join(app.root_path, 'static', 'qrcodes', f"{chave_qr}.png")
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    img.save(qr_path)

        

####################################################################################################################################
    


#####################################################################################################################################
    # Função para converter datas para formato brasileiro com segurança

    
############################################################################################################################################

    def formatar_data_mrz(data_iso):
        try:
            data_obj = datetime.strptime(data_iso, "%Y-%m-%d")
            ano = data_obj.year
            if ano < 1900:
                return "000000"
            return f"{ano % 100:02d}{data_obj.month:02d}{data_obj.day:02d}"
        except:
            return "000000"
        

        
#################################################################################################################################
    # Converter datas
    data_nascimento_br = formatar_data(dados.get('data_nascimento'))
    data_emissao_br = formatar_data(dados.get('data_emissao'))
    validade_br = formatar_data(dados.get('validade'))
    primeira_habilitacao_br = formatar_data(dados.get('primeira_habilitacao'))
###############################################################################################################################

    # Salvar imagens
    assinatura = request.files.get('assinatura')
    foto_3x4 = request.files.get('foto_3x4')

    if assinatura:
        try:
            cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
            assinatura_nome = f"{cpf}_assinatura.png"
            assinatura_path = os.path.join("C:\\Users\\anonymousof\\Pictures\\cnh_digital\\static\\assinaturas", assinatura_nome)
            os.makedirs(os.path.dirname(assinatura_path), exist_ok=True)
            assinatura.save(assinatura_path)
            print(f"✅ Assinatura salva em: {assinatura_path}")
        except Exception as e:
            print(f"❌ Erro ao salvar assinatura: {e}")

    if foto_3x4:
        try:
            cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
            foto_nome = f"{cpf}_3x4.png"
            foto_path = os.path.join("C:\\Users\\anonymousof\\Pictures\\cnh_digital\\static\\fotos", foto_nome)
            os.makedirs(os.path.dirname(foto_path), exist_ok=True)
            foto_3x4.save(foto_path)
            print(f"✅ Foto 3x4 salva em: {foto_path}")
        except Exception as e:
            print(f"❌ Erro ao salvar foto 3x4: {e}")

####################################################################################################################################    

    #url_qr = f"http://localhost:5000/consulta/{chave_qr}"

    url_qr = f" https://pierre-photoactinic-zoe.ngrok-free.dev/consulta/{chave_qr}"

    #url_qr = f"https://senatran-consulta-carteira-digital-transito.gt.tc/visualizar_cnh.php?id={chave_qr}"


    qr = qrcode.make(url_qr)
    
    
    # Gerar nome único para o QR usando CPF ou número de registro
    cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
    qr_filename = f"qr_{cpf}.png"
    
    # Caminho completo
    qr_path = os.path.join(app.root_path, 'static', 'qrcodes', qr_filename)
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    
    # Salvar imagem
    qr.save(qr_path)


####################################################################################################################################

    # Imagem de fundo da CNH
    fundo_path = os.path.join(app.root_path, 'static', 'modelo_cnh_base2.png')

##############################################################################################################################################

    # Criar pasta do usuário
    pasta_usuario = os.path.join(app.root_path, 'static', 'cnhs', usuario)
    os.makedirs(pasta_usuario, exist_ok=True)

####################################################################################################################################################

    # Gerar nome único do PDF usando CPF
    cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
    nome_arquivo = f"cnh_{cpf}.pdf"
    pdf_path = os.path.join(pasta_usuario, nome_arquivo)

#########################################################################################################################################################

    # Criar o PDF no caminho correto
    c = canvas.Canvas(pdf_path, pagesize=A4)
    largura, altura = A4

##################################################################################################################################################################

    estados_brasil = {
        "AC": "ACRE",
        "AL": "ALAGOAS",
        "AP": "AMAPÁ",
        "AM": "AMAZONAS",
        "BA": "BAHIA",
        "CE": "CEARÁ",
        "DF": "DISTRITO FEDERAL",
        "ES": "ESPÍRITO SANTO",
        "GO": "GOIÁS",
        "MA": "MARANHÃO",
        "MT": "MATO GROSSO",
        "MS": "MATO GROSSO DO SUL",
        "MG": "MINAS GERAIS",
        "PA": "PARÁ",
        "PB": "PARAÍBA",
        "PR": "PARANÁ",
        "PE": "PERNAMBUCO",
        "PI": "PIAUÍ",
        "RJ": "RIO DE JANEIRO",
        "RN": "RIO GRANDE DO NORTE",
        "RS": "RIO GRANDE DO SUL",
        "RO": "RONDÔNIA",
        "RR": "RORAIMA",
        "SC": "SANTA CATARINA",
        "SP": "SÃO PAULO",
        "SE": "SERGIPE",
        "TO": "TOCANTINS"
    }

##########################################################################################################################################################

    # Inserir imagem de fundo
    c.drawImage(fundo_path, 0, 0, width=largura, height=altura)

############################################################################################################################################################################

    # Fonte padrão para dados gerais
    c.setFont("AmrysRegular", 5)
    # Posicionamento dos dados
    c.drawString(143, 712, f"{data_nascimento_br}, {dados['local_nascimento'].upper()}, {dados['uf_nascimento'].upper()}")
    c.drawString(75, 726, f"{dados['nome_completo'].upper()}")
    c.drawString(230,  726, primeira_habilitacao_br)
    c.drawString(143, 697, data_emissao_br)
    c.drawString(143, 682, f"{dados['doc_identidade'].upper()} {dados['orgao_emissor'].upper()} {dados['uf_documento'].upper()}")
    c.drawString(143, 668, f"{dados['cpf']}")

    #RENAC E CODIGO VALIDAÇÂO NA POSIÇÂO CENTRAL CORRETA DE ACORDO COM GERADO UM EMBAIXO DO OUTRO
    largura_pagina = A4[0]
    
    renach = dados.get('numero_renach', 'UF00000000')
    codigo = dados.get('codigo_validacao', '0000000000')

    c.setFont("AmrysRegular", 5)
    c.drawCentredString(largura_pagina / 2.6, 466, codigo)
    c.drawCentredString(largura_pagina / 2.6, 458, renach)
  ################################################################################################################################################################  

    # Campos em vermelho
    c.setFillColor(red)
    c.drawString(187, 697, validade_br)
    c.drawString(193, 668, f"{dados['numero_registro']}")
    c.drawString(239, 668, f"{dados['categoria_habilitacao'].upper()}")
    c.setFillColorRGB(0, 0, 0)

#######################################################################################################################################################################
    # Número do espelho em pé SEM ESPAÇAMENTOS
    #c.saveState()
    #c.translate(55, 615)
    #c.rotate(90)
    #c.setFont("NimbusMonoBold", 8)
    #c.drawString(0, 0, f"{dados['numero_espelho'].upper()}")
    #c.restoreState()
    #c.saveState()
    #c.translate(55, 434)
    #c.rotate(90)
    #c.setFont("NimbusMonoBold", 8)
    #c.drawString(0, 0, f"{dados['numero_espelho'].upper()}")
    #c.restoreState()


    # Número do espelho em pé COM ESPAÇAMENTOS
    numero_espelho = dados.get('numero_espelho', '0000000000').upper()
    espaco = 8  # distância entre cada caractere (ajuste como quiser)

    # 🔹 Primeira posição
    c.saveState()
    c.translate(55, 615)
    c.rotate(90)
    c.setFont("NimbusMonoBold", 8)

    espaco = 5.5
    for i, char in enumerate(numero_espelho):
        c.drawString(i * espaco, 0, char)

    c.restoreState()

    # 🔹 Segunda posição
    c.saveState()
    c.translate(55, 434)
    c.rotate(90)
    c.setFont("NimbusMonoBold", 8)

    espaco = 5.5
    for i, char in enumerate(numero_espelho):
        c.drawString(i * espaco, 0, char)

    c.restoreState()
#############################################################################################################################################################################

    # Observações
    c.setFont("AmrysRegular", 5)
    observacoes = request.form.getlist('observacoes[]')# Captura múltiplas observações
    observacoes = [obs.strip() for obs in observacoes if obs.strip()][:5] # Remove campos vazios e mantém ordem

    
    y = 519 # Posição inicial no PDF

    for obs in observacoes:     # Escreve cada observação em uma linha separada
        c.drawString(73, y, obs.upper())
        y -= 5  # sobe 14 pixels por linha

 #######################################################################################################################################################################################

    # Dados adicionais
    c.drawString(144, 655, f"{dados['nacionalidade'].upper()}")
    c.drawString(144, 640, f"{dados['nome_pai'].upper()}")
    c.drawString(144, 626, f"{dados['nome_mae'].upper()}")
    # Campo de cima — mostra a sigla (ex: MG)
    c.setFont("AmrysRegular", 5)
    c.drawString(72, 458, f"{dados['local_municipio'].upper()}, {dados['local_uf'].upper()}")

 ####################################################################################################################################################################################   

    # Campo de baixo — mostra o nome completo (ex: MINAS GERAIS) com fonte personalizada
    largura_pagina = A4[0]

    estado_extenso = estados_brasil.get(dados['local_uf'].upper(), dados['local_uf'].upper())
    c.saveState()
    c.setFont("AmrysSemibold", 12)
    c.drawCentredString(largura_pagina / 4, 430, estado_extenso)
    c.restoreState()

############################################################################################################################################################################################

    # Mapeamento de siglas para nomes completos
    posicoes_categorias = {
        'ACC': (128, 583),
        'A':   (128, 575),
        'A1':  (128, 566),
        'B':   (128, 558),
        'B1':  (128, 550),
        'C':   (128, 542),
        'C1':  (128, 533),
        'D':   (229, 583),
        'D1':  (229, 575),
        'BE':  (229, 566),
        'CE':  (229, 558),
        'C1E': (229, 550),
        'DE':  (229, 542),
        'D1E': (229, 533)
    }

    categorias = request.form.getlist('categoria[]')
    validades = request.form.getlist('validade_categoria[]')

    c.setFont("Helvetica", 4)
    for cat, val in zip(categorias, validades):
        cat = cat.upper()
        if cat in posicoes_categorias and val:
            try:
                val_br = datetime.strptime(val, "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                val_br = val
            x, y = posicoes_categorias[cat]
            c.drawString(x, y, val_br)

#######################################################################################################################################################################

    # Imagens FOTO, ASSINATURA E QR
    c.drawImage(foto_path, 74, 634, width=60, height=80, mask='auto')
    c.drawImage(assinatura_path, 90, 614, width=32, height=20, mask='auto')
    c.drawImage(qr_path, 325, 535, width=220, height=220)

################################################################################################################################

    # 🔹 MRZ personalizado — estrutura visual + lógica de abreviação #CHAMA123
    c.setFont("Courier-Bold", 8)

    cpf = ''.join(filter(str.isdigit, dados.get('cpf', '')))
    registro = dados.get('numero_registro', '')[:11].ljust(13, "<")
    mrz_linha1 = f"I<BRA{registro}002".ljust(30, "<")

    def formatar_data_mrz(data_iso):
        try:
            data_obj = datetime.strptime(data_iso, "%Y-%m-%d")
            return f"{data_obj.year % 100:02d}{data_obj.month:02d}{data_obj.day:02d}"
        except:
            return "000000"

    nascimento = formatar_data_mrz(dados.get('data_nascimento'))
    validade = formatar_data_mrz(dados.get('validade'))
    sexo = dados.get('sexo', 'X')[0].upper()
    mrz_linha2 = f"{nascimento}2{sexo}{validade}BRA".ljust(29, "<") + "2"

    def formatar_nome_mrz_cnh(nome_completo):
        partes = nome_completo.upper().split()
        if not partes:
            return "D<NOME<NAO<INFORMADO<<<<<<<<<<<<<<<<<"

        primeiro_nome = partes[0]
        sobrenomes = partes[1:]

        nome_final = [primeiro_nome]

        nome_mrz_raw = "D<" + "<".join([primeiro_nome] + sobrenomes)

        if len(nome_mrz_raw) > 30:
            abreviados = []
            for i, parte in enumerate(sobrenomes):
                if i < 2:
                    abreviados.append(parte[0])
                else:
                    abreviados.append(parte)
            nome_final += abreviados
        else:
            nome_final += sobrenomes

        nome_formatado = "<".join(nome_final)
        return nome_formatado.ljust(30, "<")[:30]

    mrz_linha3 = formatar_nome_mrz_cnh(dados.get('nome_completo'))

    c.drawString(70, 300, mrz_linha1)
    c.drawString(70, 290, mrz_linha2)
    c.drawString(70, 280, mrz_linha3)

    ## 🔹 MRZ personalizado — com fonte OCRB
    #c.setFont("OCRB", 10)
    #
    #cpf = ''.join(filter(str.isdigit, dados.get('cpf', '')))
    #registro = dados.get('numero_registro', '')[:11].ljust(13, "<")
    #mrz_linha1 = f"I<BRA{registro}002".ljust(30, "<")
    #
    #def formatar_data_mrz(data_iso):
    #    try:
    #        data_obj = datetime.strptime(data_iso, "%Y-%m-%d")
    #        return f"{data_obj.year % 100:02d}{data_obj.month:02d}{data_obj.day:02d}"
    #    except:
    #        return "000000"
    #
    #nascimento = formatar_data_mrz(dados.get('data_nascimento'))
    #validade = formatar_data_mrz(dados.get('validade'))
    #sexo = dados.get('sexo', 'X')[0].upper()
    #mrz_linha2 = f"{nascimento}2{sexo}{validade}BRA".ljust(29, "<") + "2"
    #
    #def formatar_nome_mrz_cnh(nome_completo):
    #    partes = nome_completo.upper().split()
    #    if not partes:
    #        return "D<NOME<NAO<INFORMADO<<<<<<<<<<<<<<<<<"
    #
    #    primeiro_nome = partes[0]
    #    sobrenomes = partes[1:]
    #
    #    nome_final = [primeiro_nome]
    #
    #    nome_mrz_raw = "D<" + "<".join([primeiro_nome] + sobrenomes)
    #
    #    if len(nome_mrz_raw) > 30:
    #        abreviados = []
    #        for i, parte in enumerate(sobrenomes):
    #            if i < 2:
    #                abreviados.append(parte[0])
    #            else:
    #                abreviados.append(parte)
    #        nome_final += abreviados
    #    else:
    #        nome_final += sobrenomes
    #
    #    nome_formatado = "<".join(nome_final)
    #    return nome_formatado.ljust(30, "<")[:30]
    #
    #mrz_linha3 = formatar_nome_mrz_cnh(dados.get('nome_completo'))
    #
    #c.drawString(70, 300, mrz_linha1)
    #c.drawString(70, 290, mrz_linha2)
    #c.drawString(70, 280, mrz_linha3)
    #



##########################################################################################################################################################

        # Criar pasta do usuário
    pasta_usuario = os.path.join(app.root_path, 'static', 'cnhs', usuario)
    os.makedirs(pasta_usuario, exist_ok=True)

#############################################################################################################################################################

    # Gerar nome único do PDF usando CPF
    cpf = dados['cpf'].replace('.', '').replace('-', '')
    nome_arquivo = f"cnh_{cpf}.pdf"
    pdf_path = os.path.join(pasta_usuario, nome_arquivo)

####################################################################################################################################################################

    # Salvar o PDF com nome único
    c.save()  # já salva no caminho definido acima

######################################################################################################################################################################

    # Salvar CNH no JSON do usuário

        # Salvar CNH gerada
    nova_cnh = {
        'id': dados.get('numero_registro', ''),
        'nome': dados.get('nome_completo', ''),
        'uf': dados.get('local_uf', ''),
        'data': datetime.now().strftime('%d/%m/%Y'),
        'arquivo': nome_arquivo
    }

    if nova_cnh['id'] and nova_cnh['nome'] and nova_cnh['uf'] and nome_arquivo:
        salvar_cnh_do_usuario(usuario, nova_cnh)


    return redirect(url_for('visualizar_cnh'))

###############################################################################################################################################################################

@app.route('/visualizar_cnh')
def visualizar_cnh():
    usuario = session['usuario']
    cnhs = carregar_cnhs_do_usuario(usuario)
    
    if not cnhs:
        return redirect('/dashboard')  # ou mostrar uma mensagem de erro

    cnh = cnhs[-1]  # pega a última CNH gerada
    return render_template('visualizar.html', cnh=cnh, usuario=usuario)


@app.route('/consulta/<chave>')
def consulta(chave):
    try:
        with open('registros_qr.json', 'r') as f:
            registros = json.load(f)
    except FileNotFoundError:
        return "Base de dados não encontrada", 404

    dados = registros.get(chave)
    if not dados:
        return "QR inválido ou dados não encontrados", 404

    return render_template('resultado.html', dados=dados, chave_qr=chave)


#########################################################################################################################################################################################
#########################################################################################################################################################################################
# FORMULARIO MEDICO COMPLETO


@app.route('/verificar_credito_medico', methods=['POST'])
def verificar_credito_medico():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()

    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'

    custo = 40 if tipo == 'usuario' else 20
    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo:
        flash(f"Você não possui créditos suficientes para gerar um atestado. Cada atestado custa R${custo}. Seu saldo: R${saldo}.", "erro")
        return redirect('/dashboard')

    return redirect('/formulario_atestado')

@app.route('/formulario_atestado')
def formulario_atestado():
    if 'usuario' not in session:
        return redirect('/login')
    return render_template('formulario_atestado.html')





@app.route('/gerar_atestado', methods=['POST'])
def gerar_atestado():
    usuario = session['usuario']
    usuarios = carregar_usuarios()

    # 🔹 Define o custo do atestado conforme o tipo de usuário
    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'
    custo_atestado = 40 if tipo == 'usuario' else 20

    print(f"Tipo do usuário: {tipo}")

    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo_atestado:
        flash(f"Créditos insuficientes. Cada atestado custa R${custo_atestado}. Seu saldo: R${saldo}", "erro")
        return redirect('/formulario_atestado')

    # Reduz os créditos
    usuarios[usuario]['creditos'] -= custo_atestado
    salvar_usuarios(usuarios)

    nome = request.form.get("nome_paciente")
    data_hora = request.form.get("data_hora_atendimento") or ""
    data = data_hora.split("T")[0] if "T" in data_hora else ""
    horario = data_hora.split("T")[1] if "T" in data_hora else ""
    hora_liberacao = request.form.get("hora_liberacao") or ""

    # Converte a data para o formato brasileiro
    try:
        data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        data_formatada = data  # mantém original se falhar

    dias = request.form.get("dias_repouso")
    dia_inicio = request.form.get("liberado_em")  # vem como '2025-10-19'

    # Converte para formato brasileiro
    try:
        dia_inicio_formatado = datetime.strptime(dia_inicio, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        dia_inicio_formatado = dia_inicio  # mantém original se falhar

    cid = request.form.get("cid")
    cid_personalizado = request.form.get("cid_personalizado")

    # Textos automáticos por CID — estilo oficial
    cid_textos = {
        "J11": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} às {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - J11\n...........................\nCódigo da Doença",
        "A09": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} às {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - A09\n...........................\nCódigo da Doença",
        "A90": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} às {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - A90\n...........................\nCódigo da Doença",
        "H66": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} às {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - H66\n...........................\nCódigo da Doença",
        "R50": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} às {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - R50\n...........................\nCódigo da Doença"
    }

    cid_descricao = cid_textos.get(cid, cid_personalizado)

    # Captura da assinatura e posição
    assinatura_file = request.files.get("assinatura")
    assinatura_path = None
    if assinatura_file and assinatura_file.filename != "":
        assinatura_path = os.path.join(app.root_path, "static", "assinaturas", assinatura_file.filename)
        assinatura_file.save(assinatura_path)

        modelo = request.form.get("modelo_base")

        # Define posição da assinatura conforme o modelo
        if modelo == "hapvida":
            x_assinatura = 950
            y_assinatura = 1660
        elif modelo == "upa":
            x_assinatura = 1900
            y_assinatura = 2500
        else:
            x_assinatura = 950
            y_assinatura = 1850  # padrão


    dados = {
        "para": request.form.get("para"),
        "nome_paciente": nome,
        "cns": request.form.get("cns"),
        "unidade": request.form.get("unidade"),
        "data_hora_atendimento": data_hora,
        "dias_repouso": dias,
        "cid": cid,
        "cid_descricao": cid_descricao,
        "local_data": request.form.get("local_data"),
        "emissao": request.form.get("emissao"),
        "liberado_em": dia_inicio,
        "hora_liberacao": hora_liberacao,
        "medico": request.form.get("medico"),
        "crm": request.form.get("crm"),
        "rua_numero": request.form.get("rua_numero"),
        "bairro_cidade": request.form.get("bairro_cidade"),
        "cep": request.form.get("cep"),
        "assinatura_path": assinatura_path,
        "x_assinatura": x_assinatura,
        "y_assinatura": y_assinatura
    }

    chave_atestado = str(uuid.uuid4())
    modelo = request.form.get("modelo_base")
    gerar_imagem_atestado(dados, chave_atestado, modelo)

    # Salvar dados
    try:
        with open('registros_atestados.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        registros = {}

    registros[chave_atestado] = dados

    with open('registros_atestados.json', 'w', encoding='utf-8') as f:
        json.dump(registros, f, indent=4, ensure_ascii=False)

    # Gerar imagem base preenchida
    gerar_imagem_atestado(dados, chave_atestado, modelo)
    converter_png_para_pdf(chave_atestado)

    usuario = session['usuario']
    caminho_json = f'dados/{usuario}_atestados.json'
    os.makedirs('dados', exist_ok=True)

    try:
        with open(caminho_json, 'r', encoding='utf-8') as f:
            atestados = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        atestados = []

    atestados.append({
        'id': chave_atestado,
        'nome': nome,
        'cid': cid,
        'data': datetime.now().strftime('%d/%m/%Y'),
        'arquivo': f"atestado_{chave_atestado}.pdf"
    })

    with open(caminho_json, 'w', encoding='utf-8') as f:
        json.dump(atestados, f, indent=2, ensure_ascii=False)

    return redirect(url_for('visualizar_atestado', chave=chave_atestado))



@app.route('/formulario_medico/upa')
def formulario_medico_upa():
    return render_template('formulario_atestado.html', modelo_padrao='upa')

@app.route('/formulario_medico/hapvida')
def formulario_hapvida():
    return render_template('formulario_atestadohapvida.html', modelo_padrao='hapvida')




#@app.route('/gerar_atestado', methods=['POST'])
#def gerar_atestado():
#
#    usuario = session['usuario']
#    usuarios = carregar_usuarios()
#
#    # 🔹 Define o custo do atestado conforme o tipo de usuário
#    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
#    if tipo == 'cliente':
#        tipo = 'usuario'
#    custo_atestado = 40 if tipo == 'usuario' else 20
#
#    print(f"Tipo do usuário: {tipo}")
#
#    saldo = usuarios[usuario].get('creditos', 0)
#
#    if saldo < custo_atestado:
#        flash(f"Créditos insuficientes. Cada atestado custa R${custo_atestado}. Seu saldo: R${saldo}", "erro")
#        return redirect('/formulario_atestado')
#
#
#    # Reduz os créditos
#    usuarios[usuario]['creditos'] -= custo_atestado
#    salvar_usuarios(usuarios)
#
#
#    nome = request.form.get("nome_paciente")
#    data_hora = request.form.get("data_hora_atendimento") or ""
#    data = data_hora.split("T")[0] if "T" in data_hora else ""
#    horario = data_hora.split("T")[1] if "T" in data_hora else ""
#    hora_liberacao = request.form.get("hora_liberacao") or ""
#
#    
#    # Converte a data para o formato brasileiro
#    try:
#        data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
#    except:
#        data_formatada = data  # mantém original se falhar
#
#
#    dias = request.form.get("dias_repouso")
#
#    dia_inicio = request.form.get("liberado_em")  # vem como '2025-10-19'
#
#    # Converte para formato brasileiro
#    try:
#        dia_inicio_formatado = datetime.strptime(dia_inicio, "%Y-%m-%d").strftime("%d/%m/%Y")
#    except:
#        dia_inicio_formatado = dia_inicio  # mantém original se falhar
#
#
#    cid = request.form.get("cid")
#    cid_personalizado = request.form.get("cid_personalizado")
#
#    # Textos automáticos por CID — estilo oficial
#    cid_textos = {
#        "J11": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} ás {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - J11\n...........................\nCódigo da Doença",
#        "A09": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} ás {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - A09\n...........................\nCódigo da Doença",
#        "A90": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} ás {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - A90\n...........................\nCódigo da Doença",
#        "H66": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} ás {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - H66\n...........................\nCódigo da Doença",
#        "R50": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\naté o dia {dia_inicio_formatado} ás {hora_liberacao} tendo como causa do atendimento o código abaixo:\n\nCID 10 - R50\n...........................\nCódigo da Doença"
#    }
#
#    #cid_textos = {
#    #    "J11": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\na partir de {dia_inicio_formatado}, tendo como causa do atendimento o código abaixo:\n\nCID 10 - J11\n...........................\nCódigo da Doença",
#    #    "A09": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\na partir de {dia_inicio_formatado}, tendo como causa do atendimento o código abaixo:\n\nCID 10 - A09\n...........................\nCódigo da Doença",
#    #    "A90": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\na partir de {dia_inicio_formatado}, tendo como causa do atendimento o código abaixo:\n\nCID 10 - A90\n...........................\nCódigo da Doença",
#    #    "H66": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\na partir de {dia_inicio_formatado}, tendo como causa do atendimento o código abaixo:\n\nCID 10 - H66\n...........................\nCódigo da Doença",
#    #    "R50": f"Atesto que atendi em {data_formatada} o(a) Sr(a) {nome} às {horario},\nsendo necessário seu afastamento do local de trabalho ou escola por {dias} dia(s),\na partir de {dia_inicio_formatado}, tendo como causa do atendimento o código abaixo:\n\nCID 10 - R50\n...........................\nCódigo da Doença"
#    #}
#
#
#
#    cid_descricao = cid_textos.get(cid, cid_personalizado)
#
#
#
#    dados = {
#        "para": request.form.get("para"),
#        "nome_paciente": nome,
#        "cns": request.form.get("cns"),
#        "unidade": request.form.get("unidade"),
#        "data_hora_atendimento": data_hora,
#        "dias_repouso": dias,
#        "cid": cid,
#        "cid_descricao": cid_descricao,
#        "local_data": request.form.get("local_data"),
#        "emissao": request.form.get("emissao"),
#        "liberado_em": dia_inicio,
#        "hora_liberacao": request.form.get("hora_liberacao"),
#        "medico": request.form.get("medico"),
#        "crm": request.form.get("crm"),
#        "rua_numero": request.form.get("rua_numero"),
#        "bairro_cidade": request.form.get("bairro_cidade"),
#        "cep": request.form.get("cep")
#    }
#
#    chave_atestado = str(uuid.uuid4())
#
#
#    modelo = request.form.get("modelo_base")
#    gerar_imagem_atestado(dados, chave_atestado, modelo)
#
#    # Salvar dados
#    try:
#        with open('registros_atestados.json', 'r', encoding='utf-8') as f:
#            registros = json.load(f)
#    except (FileNotFoundError, json.JSONDecodeError):
#        registros = {}
#
#    registros[chave_atestado] = dados
#
#    with open('registros_atestados.json', 'w', encoding='utf-8') as f:
#        json.dump(registros, f, indent=4, ensure_ascii=False)
#
#    # Gerar imagem base preenchida
#    gerar_imagem_atestado(dados, chave_atestado, modelo)
#    converter_png_para_pdf(chave_atestado)
#
#
#    usuario = session['usuario']
#    caminho_json = f'dados/{usuario}_atestados.json'
#    os.makedirs('dados', exist_ok=True)
#
#    try:
#        with open(caminho_json, 'r', encoding='utf-8') as f:
#            atestados = json.load(f)
#    except (FileNotFoundError, json.JSONDecodeError):
#        atestados = []
#
#    atestados.append({
#        'id': chave_atestado,
#        'nome': nome,
#        'cid': cid,
#        'data': datetime.now().strftime('%d/%m/%Y'),
#        'arquivo': f"atestado_{chave_atestado}.pdf"
#    })
#
#    with open(caminho_json, 'w', encoding='utf-8') as f:
#        json.dump(atestados, f, indent=2, ensure_ascii=False)
#
#
#    return redirect(url_for('visualizar_atestado', chave=chave_atestado))
#
#








def gerar_imagem_atestado(dados, chave, modelo):
    import locale
    from datetime import datetime
    from PIL import Image, ImageDraw, ImageFont
    import os
    from flask import session

    # Escolhe a imagem base conforme o modelo
    if modelo == "hapvida":
        base_path = os.path.join(app.root_path, "static", "base_atestadohap.png")
    else:
        base_path = os.path.join(app.root_path, "static", "base_atestado1.png")

    base = Image.open(base_path).convert("RGB")
    draw = ImageDraw.Draw(base)



    if dados.get("assinatura_path"):
        try:
            assinatura_img = Image.open(dados["assinatura_path"]).convert("RGBA")
            assinatura_img = assinatura_img.resize((250, 300))  # ajuste conforme necessário

            x = int(dados.get("x_assinatura", 950))
            y = int(dados.get("y_assinatura", 2000))

            base.paste(assinatura_img, (x, y), assinatura_img)
            print("✅ Assinatura colada na imagem.")
        except Exception as e:
            print("⚠️ Erro ao colar assinatura:", e)    


    # Fontes
    fonte = ImageFont.truetype("arial.ttf", 55)
    fonte_trivia = ImageFont.truetype(os.path.join(app.root_path, "static", "fonts", "TriviaSlabRegular.ttf"), 43)
    fonte_pequena = ImageFont.truetype("arial.ttf", 28)

    # Formata datas
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

    try:
        dt_emissao = datetime.fromisoformat(dados['emissao'])
        emissao_formatada = dt_emissao.strftime('%d de %B de %Y')
    except:
        emissao_formatada = dados['emissao']

    try:
        dt_atendimento = datetime.fromisoformat(dados['data_hora_atendimento'])
        atendimento_formatado = dt_atendimento.strftime('%d/%m/%Y %H:%M')
    except:
        atendimento_formatado = dados['data_hora_atendimento']

    # Layout por modelo
    if modelo == "hapvida":
        #draw.text((280, 680), f"PARA: {dados['para']}", fill="black", font=fonte)
        #draw.text((150, 3400), f"{dados['rua_numero']},{dados['bairro_cidade']}CEP: {dados['cep']}", fill="black", font=fonte)
       
        # Separa o texto principal do CID
        texto_principal = dados["cid_descricao"].split("CID 10")[0].strip()
        cid_codigo = dados["cid"]
        cid_bloco = f"CID 10 - {cid_codigo}\n...........................\nCódigo da Doença"

        # Quebra o texto principal em linhas
        texto_formatado = textwrap.fill(texto_principal, width=70)

        # Junta tudo com quebra de linha
        texto_final = f"{texto_formatado}\n\n{cid_bloco}"

        # Desenha na imagem
        draw.multiline_text((130, 650), texto_final, fill="black", font=fonte, spacing=4)







        draw.text((1600, 2300), f"{atendimento_formatado}", fill="black", font=fonte)
        draw.multiline_text((190, 2300), f"{dados['medico']}", fill="black", font=fonte)
        
       
        # Texto do carimbo
        # Cria uma versão maior da fonte
        fonte_trivia_maior = ImageFont.truetype(os.path.join(app.root_path, "static", "fonts", "TriviaSlabRegular.ttf"), 50)
        # Texto do carimbo
        texto_carimbo = f"Dr. {dados['medico']}\nClínico e Cirurgião Geral\nCRM {dados['crm']} - Médico"      
        # Calcula o tamanho necessário do texto
        bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), texto_carimbo, font=fonte_trivia_maior, spacing=4)
        largura_texto = bbox[2] - bbox[0]
        altura_texto = bbox[3] - bbox[1] 
        # Cria imagem auxiliar com espaço suficiente
        texto_img = Image.new("RGBA", (largura_texto + 20, altura_texto + 20), (255, 255, 255, 0))
        texto_draw = ImageDraw.Draw(texto_img)
        # Desenha o texto com fonte maior e cor #3C3C3C
        texto_draw.multiline_text((10, 10), texto_carimbo, fill="#3C3C3C", font=fonte_trivia_maior, spacing=4)
        # Gira o texto levemente
        texto_rotacionado = texto_img.rotate(5, expand=True)
        # Cola na imagem principal
        x_destino = 850
        y_destino = 1755
        base.paste(texto_rotacionado, (x_destino, y_destino), texto_rotacionado)




        # Obtém o texto que será desenhado
        texto = f"{dados['cns']}, {emissao_formatada}."
        # Calcula a largura do texto
        bbox = draw.textbbox((0, 0), texto, font=fonte)
        largura_texto = bbox[2] - bbox[0]  # largura = x_max - x_min
        # Obtém a largura da imagem
        largura_imagem = base.size[0]
        # Calcula a posição X centralizada
        x_central = (largura_imagem - largura_texto) // 2
        # Desenha o texto centralizado horizontalmente
        draw.text((x_central, 1400), texto, fill="black", font=fonte)


    else:
        draw.text((280, 900), f"PARA: {dados['para']}", fill="black", font=fonte)


        
        
        # Separa o texto principal do CID
        texto_principal = dados["cid_descricao"].split("CID 10")[0].strip()
        cid_codigo = dados["cid"]
        cid_bloco = f"CID 10 - {cid_codigo}\n...........................\nCódigo da Doença"
        
        # Quebra o texto principal em linhas
        texto_formatado = textwrap.fill(texto_principal, width=85)
        
        # Junta tudo com quebra de linha
        texto_final = f"{texto_formatado}\n\n{cid_bloco}"
        
        # Desenha na imagem
        draw.multiline_text((130, 1000), texto_final, fill="black", font=fonte, spacing=4)
        





        draw.text((840, 255), f"{dados['rua_numero']},\n{dados['bairro_cidade']}\nCEP: {dados['cep']}", fill="black", font=fonte)
        draw.text((1500, 1800), f"{dados['unidade']}, {emissao_formatada}", fill="black", font=fonte)
        draw.multiline_text((1830, 2635), f"Dr. {dados['medico']}\n          Médico\n   CRM: {dados['crm']}", fill="black", font=fonte_trivia, spacing=4)
        draw.text((125, 2790), f"Emitido em: {atendimento_formatado}", fill="black", font=fonte_pequena)

    # Salva imagem e PDF
    usuario = session['usuario']
    output_dir = os.path.join(app.root_path, "static", "atestados", usuario)
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{chave}.png")
    base.save(output_path)

    pdf_path = os.path.join(output_dir, f"atestado_{chave}.pdf")
    base.save(pdf_path, "PDF", resolution=25.0)








#def gerar_imagem_atestado(dados, chave, modelo):
#
#    
#    if modelo == "hapvida":
#        base_path = os.path.join(app.root_path, "static", "base_atestadohap.png")
#    else:
#        base_path = os.path.join(app.root_path, "static", "base_atestado1.png")
#
#    base = Image.open(base_path).convert("RGB")
#    draw = ImageDraw.Draw(base)
#
#    
#    fonte = ImageFont.truetype("arial.ttf", 55)
#    fonte_trivia = ImageFont.truetype(os.path.join(app.root_path, "static", "fonts", "TriviaSlabRegular.ttf"), 43)
#    fonte_pequena = ImageFont.truetype("arial.ttf", 28)
#
#    
#    #draw.text((50, 110), f"Nome da Paciente: {dados['nome_paciente']}", fill="black", font=fonte)
#    #draw.text((50, 140), f"CNS: {dados['cns']}", fill="black", font=fonte)
#    #draw.text((50, 200), f"Atendimento: {dados['data_hora_atendimento']}", fill="black", font=fonte)
#    #draw.text((50, 230), f"Repouso: {dados['dias_repouso']} dia(s)", fill="black", font=fonte)
#    #draw.text((50, 360), f"Local/Data: {dados['local_data']}", fill="black", font=fonte)
#    #draw.text((50, 420), f"Liberado em: {dados['liberado_em']} às {dados['hora_liberacao']}", fill="black", font=fonte)
#
#    draw.text((280, 900), f"PARA: {dados['para']}", fill="black", font=fonte)
#    
#    draw.multiline_text((130, 1000), dados['cid_descricao'], fill="black", font=fonte, spacing=4)
#
#    draw.text((840, 255), f"{dados['rua_numero']},\n{dados['bairro_cidade']}\nCEP: {dados['cep']}", fill="black", font=fonte)
#
#
#    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
#
#    try:
#        dt_emissao = datetime.fromisoformat(dados['emissao'])
#        emissao_formatada = dt_emissao.strftime('%d de %B de %Y.')
#    except:
#        emissao_formatada = dados['emissao']  # fallback se der erro
#
#    draw.text((1500, 1800), f"{dados['unidade']}, {emissao_formatada}", fill="black", font=fonte)
#
#
#    draw.multiline_text((1830, 2635), f"Dr. {dados['medico']}\n          Médico\n   CRM: {dados['crm']}", fill="black", font=fonte_trivia, spacing=4)
#
#
#
#    # Converter e formatar EMITIDO EM
#    try:
#        dt = datetime.fromisoformat(dados['data_hora_atendimento'])
#        data_formatada = dt.strftime("%d/%m/%Y %H:%M")
#    except:
#        data_formatada = dados['data_hora_atendimento']  # fallback se der erro
#
#    draw.text((125, 2790), f"Emitido em: {data_formatada}", fill="black", font=fonte_pequena)
#
#
#    usuario = session['usuario']
#    output_dir = os.path.join(app.root_path, "static", "atestados", usuario)
#    os.makedirs(output_dir, exist_ok=True)
#
#    output_path = os.path.join(output_dir, f"{chave}.png")
#    base.save(output_path)
#
#    pdf_path = os.path.join(output_dir, f"atestado_{chave}.pdf")
#    base.save(pdf_path, "PDF", resolution=25.0)
#











@app.route('/baixar_atestado/<usuario>/<nome_arquivo>')
def baixar_atestado(usuario, nome_arquivo):
    pasta = os.path.join(app.root_path, 'static', 'atestados', usuario)
    return send_from_directory(pasta, nome_arquivo, as_attachment=True)

@app.route('/excluir_atestado/<id>', methods=['POST'])
def excluir_atestado(id):
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']

    # 🔹 Remove do JSON completo
    try:
        with open('registros_atestados.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        registros = {}

    if id in registros:
        del registros[id]
        with open('registros_atestados.json', 'w', encoding='utf-8') as f:
            json.dump(registros, f, indent=2, ensure_ascii=False)

    # 🔹 Remove do JSON que alimenta a tela
    caminho_resumo = f'dados/{usuario}_atestados.json'
    try:
        with open(caminho_resumo, 'r', encoding='utf-8') as f:
            atestados = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        atestados = []

    # Remove o atestado com o ID correspondente
    atestados = [a for a in atestados if str(a.get('id')) != str(id)]

    with open(caminho_resumo, 'w', encoding='utf-8') as f:
        json.dump(atestados, f, indent=2, ensure_ascii=False)

    # 🔹 Apaga arquivos
    output_dir = os.path.join(app.root_path, "static", "atestados", usuario)
    pdf_path = os.path.join(output_dir, f"atestado_{id}.pdf")
    png_path = os.path.join(output_dir, f"{id}.png")

    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    if os.path.exists(png_path):
        os.remove(png_path)

    flash("Atestado excluído com sucesso!", "sucesso")
    return redirect('/atestados_salvos')





@app.route('/visualizar_atestado')
def visualizar_atestado():
    if 'usuario' not in session:
        return redirect('/login')

    chave = request.args.get('chave')
    usuario = session['usuario']

    nome_arquivo = f"atestado_{chave}.pdf"
    pasta_usuario = os.path.join(app.root_path, "static", "atestados", usuario)
    pdf_path = os.path.join(pasta_usuario, nome_arquivo)

    if not os.path.exists(pdf_path):
        return f"❌ Arquivo não encontrado"

    # Renderiza a página com o iframe
    return render_template('visualizar_atestado.html', usuario=usuario, chave=chave)

@app.route('/arquivo_atestado')
def arquivo_atestado():
    if 'usuario' not in session:
        return redirect('/login')

    chave = request.args.get('chave')
    usuario = session['usuario']

    nome_arquivo = f"atestado_{chave}.pdf"
    pasta_usuario = os.path.join(app.root_path, "static", "atestados", usuario)
    pdf_path = os.path.join(pasta_usuario, nome_arquivo)

    if os.path.exists(pdf_path):
        # Mostra o PDF diretamente (sem baixar)
        return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)
    else:
        return f"❌ PDF não encontrado: {pdf_path}", 404








def converter_png_para_pdf(chave):
    from flask import session

    usuario = session['usuario']
    output_dir = os.path.join(app.root_path, "static", "atestados", usuario)
    os.makedirs(output_dir, exist_ok=True)

    png_path = os.path.join(output_dir, f"{chave}.png")
    pdf_path = os.path.join(output_dir, f"atestado_{chave}.pdf")

    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(png_path))


@app.route('/atestados_salvos')
def atestados_salvos():
    if 'usuario' not in session:
        return redirect('/login')

    caminho_json = 'registros_atestados.json'

    try:
        with open(caminho_json, 'r') as f:
            dados = json.load(f)
            if isinstance(dados, dict):
                atestados = []
                for id, info in dados.items():
                    info['id'] = id
                    atestados.append(info)
            elif isinstance(dados, list):
                atestados = dados
            else:
                atestados = []
    except (FileNotFoundError, json.JSONDecodeError):
        atestados = []

    return render_template('atestados_salvos.html', atestados=atestados)


##########################################################################################

@app.route('/perfil')
def perfil():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']

    with open('usuarios.json', 'r') as f:
        usuarios = json.load(f)

    dados = usuarios.get(usuario, {})

    return render_template('perfil.html', usuario=usuario, dados=dados)


def adicionar_credito(usuario, valor):
    with open('usuarios.json', 'r') as f:
        usuarios = json.load(f)

    if usuario not in usuarios:
        return False

    # Atualiza saldo
    usuarios[usuario]['creditos'] += valor

    # Garante que o histórico existe
    if 'historico_creditos' not in usuarios[usuario]:
        usuarios[usuario]['historico_creditos'] = []

    # Adiciona nova entrada com data atual
    usuarios[usuario]['historico_creditos'].append({
        "valor": valor,
        "data": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

    # Salva no JSON
    with open('usuarios.json', 'w') as f:
        json.dump(usuarios, f, indent=2)

    return True



@app.route('/admin/recarregar', methods=['POST'])
def painel_recarregar():
    if 'usuario' not in session or session['usuario'] != 'admin':
        return redirect('/login')

    usuario_destino = request.form['usuario']
    valor = int(request.form['valor'])

    sucesso = adicionar_credito(usuario_destino, valor)

    if sucesso:
        flash(f'R$ {valor} adicionados para {usuario_destino}.', 'sucesso')
    else:
        flash('Usuário não encontrado.', 'erro')

    return redirect('/admin')

from datetime import datetime
import json

from datetime import datetime
import json

def registrar_credito(usuario, novo_valor):
    caminho = 'usuarios.json'

    with open(caminho, 'r') as f:
        usuarios = json.load(f)

    if usuario not in usuarios:
        return False

    dados = usuarios[usuario]
    saldo_antigo = dados.get('creditos', 0)
    valor_adicionado = novo_valor - saldo_antigo

    # Atualiza o saldo
    dados['creditos'] = novo_valor

    # Só registra se houve adição
    if valor_adicionado > 0:
        if 'historico_creditos' not in dados:
            dados['historico_creditos'] = []

        dados['historico_creditos'].append({
            "valor": valor_adicionado,
            "data": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    # Atualiza o dicionário principal
    usuarios[usuario] = dados

    # Salva no JSON
    with open(caminho, 'w') as f:
        json.dump(usuarios, f, indent=2)

    return True


@app.route('/admin/atualizar_credito', methods=['POST'])
def atualizar_credito():
    usuario_destino = request.form['editar_usuario']
    novo_valor = int(request.form['novo_credito'])

    registrar_credito(usuario_destino, novo_valor)

    return redirect('/admin')

@app.route('/ver_perfil')
def ver_perfil():
    usuarios = carregar_usuarios()  # 👈 carrega os dados direto do JSON

    if 'usuario' not in session or usuarios[session['usuario']]['tipo'] != 'admin':
        return redirect('/login')

    usuario_alvo = request.args.get('usuario')
    if usuario_alvo not in usuarios:
        return "Usuário não encontrado", 404

    dados = usuarios[usuario_alvo]
    return render_template('perfil.html', usuario=usuario_alvo, dados=dados)


@app.route('/trocar_senha', methods=['POST'])
def trocar_senha():
    print("Recebendo troca de senha...") 
    usuarios = carregar_usuarios()
    usuario = request.form.get('usuario_troca')
    nova_senha = request.form.get('nova_senha')

    if usuario in usuarios:
        usuarios[usuario]['senha'] = nova_senha
        salvar_usuarios(usuarios)
        return redirect('/admin')
    else:
        return "Usuário não encontrado", 404


########################## RG #######################################################################################################

@app.route('/formulario_rg')
def formulario_rg():
    if 'usuario' not in session:
        return redirect('/login')
    return render_template('FormularioRG.html')


def formatar_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, cpf))  # remove qualquer caractere não numérico
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"



@app.route('/gerar_rg', methods=['POST'])
def gerar_rg():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()

    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'

    custo_rg = 40 if tipo == 'usuario' else 20
    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo_rg:
        return f"Créditos insuficientes. Cada RG custa R${custo_rg}. Seu saldo: R${saldo}"

    usuarios[usuario]['creditos'] -= custo_rg
    salvar_usuarios(usuarios)

    dados = request.form.to_dict()
    cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
    nome_arquivo = f"rg_{cpf}.pdf"

    pasta_usuario = os.path.join(app.root_path, 'static', 'rgs', usuario)
    os.makedirs(pasta_usuario, exist_ok=True)
    caminho_pdf = os.path.join(pasta_usuario, nome_arquivo)

    # 🔹 Salvar arquivos enviados
    nome_foto = f"{cpf}_3x4.png"
    nome_assinatura = f"{cpf}_assinatura.png"
    caminho_foto = os.path.join(pasta_usuario, nome_foto)
    caminho_assinatura = os.path.join(pasta_usuario, nome_assinatura)

    if 'foto_3x4' in request.files:
        request.files['foto_3x4'].save(caminho_foto)

    if 'assinatura' in request.files:
        request.files['assinatura'].save(caminho_assinatura)

    # 🔹 Fundir imagens transparentes na base
    base_path = os.path.join(app.root_path, 'static', 'base_RG2.png')
    base_final_path = os.path.join(pasta_usuario, f"{cpf}_base_final.png")

    base = Image.open(base_path).convert("RGBA")
    foto = Image.open(caminho_foto).convert("RGBA").resize((280, 330))
    assinatura = Image.open(caminho_assinatura).convert("RGBA").resize((160, 110))
    base.paste(foto, (170, 660), mask=foto)

    ### SEGUNDA FOTO MENOR
    foto = Image.open(caminho_foto).convert("RGBA").resize((80, 100))
    base.paste(foto, (1245, 1390), mask=foto)
    ###################################

    base.paste(assinatura, (600, 1025), mask=assinatura)
    
    ###############ASSINATURA 2 ####################################################
    
    base.paste(assinatura, (250, 2510), mask=assinatura)
    ################################################################################

    base.save(base_final_path)
    
    ############

    # 🔹 Gerar chave QR primeiro
    chave_qr = str(uuid.uuid4())
    
    # Gerar imagem do QR com a chave
    #url_rg = f"http://192.168.0.101:5000/rg/{chave_qr}"

    url_rg = f"https://pierre-photoactinic-zoe.ngrok-free.dev/rg_qr/{chave_qr}"

    qr = qrcode.make(url_rg)
    qr_buffer = BytesIO()
    qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    qr_image = ImageReader(qr_buffer)



    # 🔹 Formatar campos
    data_nasc = formatar_data_brasil(dados.get('data_nascimento'))
    data_validade = formatar_data_brasil(dados.get('data_validade'))
    data_emissao = formatar_data_brasil(dados.get('data_emissao'))
    cpf_formatado = formatar_cpf(cpf)
    codigo_pais = extrair_codigo_pais(dados.get('nacionalidade'))


    mrz = gerar_mrz(
        cpf_formatado,
        dados.get('data_nascimento'),
        dados.get('sexo'),
        dados.get('data_validade'),
        dados.get('nacionalidade'),
        dados.get('nome')
    )

    

    # ✅ Gerar PDF com ReportLab
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    c.drawImage(base_final_path, x=0, y=0, width=595, height=842)

    c.setFont("Helvetica", 7)
    c.drawString(164, 715,  f"{dados.get('naturalidade')}")
    c.setFont("Helvetica", 6)
    c.drawString(124, 673, f"{dados.get('nome')}")

    c.setFont("Helvetica", 8)
    c.drawString(124, 627, f"{cpf_formatado}")
    c.setFont("Helvetica", 6)

    c.drawString(124, 612, f"{data_nasc}")
    c.drawString(124, 596,  f"{dados.get('naturalidade')}")
    c.drawString(227, 629, f"{dados.get('sexo')}")
    c.drawString(227, 612, f"{codigo_pais}")
    c.drawString(227, 597, f"{data_validade}")
    
    c.drawString(118, 505, f"{dados.get('nome_pai')}")
    c.drawString(118, 496, f"{dados.get('nome_mae')}")
    
    c.drawString(118, 468, f"{dados.get('orgao_expedidor')}")
    c.drawString(118, 445, f"{dados.get('local')}")
    c.drawString(246, 444, f"{data_emissao}")
    c.drawString(38, 254,  f"{dados.get('estado_civil')}")
    c.drawString(226, 273, f"{dados.get('tipo_sanguineo')}")
    c.drawString(226, 254,f"{dados.get('doador')}")
    c.drawString(165, 231,f"{dados.get('certidao')}")

     # Inserir QR no PDF
    c.drawImage(qr_image, x=378, y=560, width=180, height=180)
    # Inserir QR no PDF 2
    c.drawImage(qr_image, x=43, y=445, width=60, height=60)


    # Define a cor #333333
    mrz_color = Color(0.2, 0.2, 0.2)
    
    # Aplica antes de desenhar o MRZ
    c.setFont("OCRB", 10)
    c.setFillColor(mrz_color)
    c.drawString(50, 380, mrz.split('\n')[0])
    c.drawString(50, 364, mrz.split('\n')[1])
    c.drawString(50, 349, mrz.split('\n')[2])

    c.save()

   

    dados_resultado = {
        "nome": dados.get("nome"),
        "cpf": cpf,
        "data_nascimento": formatar_data_brasileira(dados.get("data_nascimento")),
        "naturalidade": dados.get("naturalidade"),
        "sexo": dados.get("sexo"),
        "nacionalidade": dados.get("nacionalidade"),
        "data_validade": formatar_data_brasileira(dados.get("data_validade")),
        "estado": dados.get("estado"),
        "nome_mae": dados.get("nome_mae"),
        "nome_pai": dados.get("nome_pai"),
        "orgao_expedidor": dados.get("orgao_expedidor"),
        "local": dados.get("local"),
        "data_emissao": formatar_data_brasileira(dados.get("data_emissao")),
        "estado_civil": dados.get("estado_civil"),
        "tipo_sanguineo": dados.get("tipo_sanguineo"),
        "doador": dados.get("doador"),
        "certidao": dados.get("certidao"),
        "arquivo": nome_arquivo,
        "edicoes": 0,
        "foto": f"/static/rgs/{usuario}/{nome_foto}",
        "assinatura": f"/static/rgs/{usuario}/{nome_assinatura}"
    }


    # 🔹 Salvar no registros_rg.json
    try:
        with open('registros_rg.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        registros = {}

    cpf_atual = dados_resultado.get("cpf")
    chave_existente = None

    for chave, registro in registros.items():
        if registro.get("cpf") == cpf_atual:
            chave_existente = chave
            break

    #if chave_existente:
    #    edicoes = registros[chave_existente].get("edicoes", 0)
    #    if edicoes >= 1:
    #        return render_template('FormularioRG.html', dados=dados_resultado, erro="Este CPF já foi editado uma vez. Não é possível editar novamente.")
    #    else:
    #        dados_resultado["edicoes"] = edicoes + 1
    #        chave_qr = chave_existente
    #else:
    #    dados_resultado["edicoes"] = 0
    #    chave_qr = str(uuid.uuid4())

    registros[chave_qr] = dados_resultado

    with open('registros_rg.json', 'w', encoding='utf-8') as f:
        json.dump(registros, f, indent=4, ensure_ascii=False)

    return redirect(url_for('visualizar_rg', chave=chave_qr))






def formatar_data_brasileira(data_iso):
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return data_iso



def extrair_codigo_pais(texto):
    if "(" in texto and ")" in texto:
        return texto.split("(")[-1].split(")")[0].strip()
    return texto.strip()



#def formatar_nome_mrz(nome_completo):
#    partes = nome_completo.upper().split()
#    if not partes:
#        return "NOME<NAO<INFORMADO"
#
#    nome_final = []
#    nome_final.append(partes[0])  # Primeiro nome
#
#    sobrenomes = partes[1:]
#
#    # Se o nome completo for muito longo, abrevia os dois primeiros sobrenomes
#    if len("D<" + "<".join(partes).replace(" ", "<")) > 30:
#        for i, parte in enumerate(sobrenomes):
#            if i < 2:
#                nome_final.append(parte[0])  # abrevia
#            else:
#                nome_final.append(parte)     # mantém completo
#    else:
#        nome_final.extend(sobrenomes)
#
#    nome_mrz = "<".join(nome_final)[:28]  # garante limite
#    return f"D<{nome_mrz}".ljust(30, "<")

#def formatar_nome_mrz(nome_completo):
#    partes = nome_completo.upper().split()
#    if not partes:
#        return "D<NOME<NAO<INFORMADO<<<<<<<<<<<<<<<<<"
#
#    nome_final = [partes[0]]  # Primeiro nome completo
#    sobrenomes = partes[1:]
#
#    # Monta nome com abreviação dos dois primeiros sobrenomes se necessário
#    nome_mrz_raw = "D<" + "<".join(partes)
#    if len(nome_mrz_raw) > 30:
#        for i, parte in enumerate(sobrenomes):
#            if i < 2:
#                nome_final.append(parte[0])  # abrevia para a primeira letra
#            else:
#                nome_final.append(parte)     # mantém completo
#    else:
#        nome_final.extend(sobrenomes)
#
#    nome_mrz = "<".join(nome_final)
#    linha3 = f"D<{nome_mrz}".ljust(30, "<")[:30]  # garante 30 exatos
#    return linha3


def formatar_nome_mrz(nome_completo):
    partes = nome_completo.upper().split()
    if not partes:
        return "D<NOME<NAO<INFORMADO<<<<<<<<<<<<<<<<<"

    nome_final = []

    # Primeiro nome sempre completo
    nome_final.append(partes[0])

    sobrenomes = partes[1:]

    # Se houver exatamente 2 sobrenomes, insere << entre eles
    if len(sobrenomes) == 2:
        nome_final.append(sobrenomes[0])
        nome_final.append("")  # gera << no MRZ
        nome_final.append(sobrenomes[1])
    else:
        # Se nome for longo, abrevia os dois primeiros sobrenomes
        nome_mrz_raw = "D<" + "<".join(partes)
        if len(nome_mrz_raw) > 30:
            for i, parte in enumerate(sobrenomes):
                if i < 2:
                    nome_final.append(parte[0])  # abrevia
                else:
                    nome_final.append(parte)
        else:
            nome_final.extend(sobrenomes)

    nome_mrz = "<".join(nome_final)
    linha3 = f"D<{nome_mrz}".ljust(30, "<")[:30]
    return linha3


def gerar_mrz(cpf, nascimento, sexo, validade, nacionalidade, nome_completo):
    doc_type = "ID"
    pais = "BRA"
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    linha1_raw = f"{doc_type}{pais}{cpf_limpo}{cpf_limpo}<<0"
    linha1 = linha1_raw.ljust(30, "<")

    try:
        nascimento_fmt = datetime.strptime(nascimento, "%Y-%m-%d").strftime("%y%m%d")
        validade_fmt = datetime.strptime(validade, "%Y-%m-%d").strftime("%y%m%d")
    except:
        nascimento_fmt = "000000"
        validade_fmt = "000000"

    sexo_mrz = sexo[0].upper() if sexo else "X"
    nacionalidade_mrz = extrair_codigo_pais(nacionalidade)
    linha2_raw = f"{nascimento_fmt}{sexo_mrz}{validade_fmt}{nacionalidade_mrz}"
    linha2 = linha2_raw.ljust(29, "<") + "2"  # total 30

    nome_mrz = nome_completo.upper().replace(" ", "<")[:28]  # limita a 28
    linha3_raw = f"D<{nome_mrz}"
    linha3 = formatar_nome_mrz(nome_completo)



    return f"{linha1}\n{linha2}\n{linha3}"



@app.route('/rg_qr/<chave>')
def rg_qr(chave):
    try:
        with open('registros_rg.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except FileNotFoundError:
        registros = {}

    dados = registros.get(chave)
    if not dados:
        abort(404)

    # Adiciona campo 'hash' se quiser gerar dinamicamente
    if 'hash' not in dados:
        import hashlib
        hash_str = json.dumps(dados, ensure_ascii=False).encode('utf-8')
        dados['hash'] = hashlib.md5(hash_str).hexdigest()

    # Adiciona campo 'nome_social' se não existir
    if 'nome_social' not in dados:
        dados['nome_social'] = None

    return render_template('rg_qr.html', dados=dados)

def formatar_data_brasil(data_iso):
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        return data_iso  # se der erro, retorna como está
    

def remover_transparencia(origem, destino, tamanho=None):
    img = Image.open(origem)
    if img.mode in ('RGBA', 'LA'):
        fundo = Image.new("RGB", img.size, (255, 255, 255))
        fundo.paste(img, mask=img.split()[3])  # usa canal alpha como máscara
        if tamanho:
            fundo = fundo.resize(tamanho)
        fundo.save(destino)
    else:
        img.convert("RGB").save(destino)



@app.route('/arquivo_rg')
def arquivo_rg():
    chave = request.args.get('chave')
    try:
        with open('registros_rg.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        registros = {}

    dados = registros.get(chave)
    if not dados:
        return "Arquivo não encontrado."

    usuario = session.get('usuario')
    nome_arquivo = dados.get('arquivo')
    caminho_pdf = os.path.join(app.root_path, 'static', 'rgs', usuario, nome_arquivo)

    return send_file(caminho_pdf, mimetype='application/pdf')




@app.route('/rgs_salvos')
def rgs_salvos():
    try:
        with open('registros_rg.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except FileNotFoundError:
        registros = {}

    rgs = []
    for chave, dados in registros.items():
        rgs.append({
            'chave': chave,
            'nome': dados.get('nome', 'Sem nome'),
            'numero': dados.get('cpf', chave),
            'data_emissao': dados.get('data_emissao', 'Data desconhecida'),
            'arquivo': dados.get('arquivo', f'rg_{chave}.pdf')
        })

    return render_template('rgs_salvos.html', rgs=rgs)


@app.route('/baixar_rg/<chave>')
def baixar_rg(chave):
    try:
        with open('registros_rg.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except:
        return "Arquivo de dados não encontrado."

    if chave not in registros:
        return "Registro não encontrado."

    caminho = os.path.join(app.root_path, 'static', 'rgs', 'admin', registros[chave]['arquivo'])
    return send_file(caminho, mimetype='application/pdf', as_attachment=True)


@app.route('/excluir_rg/<chave>', methods=['POST'])
def excluir_rg(chave):
    try:
        with open('registros_rg.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except:
        registros = {}

    if chave not in registros:
        flash('Registro não encontrado.', 'erro')
        return redirect(url_for('rgs_salvos'))

    caminho = os.path.join(app.root_path, 'static', 'rgs', 'admin', registros[chave]['arquivo'])
    try:
        os.remove(caminho)
    except:
        pass

    registros.pop(chave)

    with open('registros_rg.json', 'w', encoding='utf-8') as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)

    flash('RG excluído com sucesso!', 'sucesso')
    return redirect(url_for('rgs_salvos'))


@app.route('/visualizar_rg/<chave>')
def visualizar_rg(chave):
    try:
        with open('registros_rg.json', 'r', encoding='utf-8') as f:
            registros = json.load(f)
    except:
        return "Arquivo de dados não encontrado."

    if chave not in registros:
        return "Registro não encontrado."

    dados = registros[chave]
    return render_template('visualizar_rg.html', dados=dados, chave=chave)


@app.route('/verificar_credito_rg', methods=['POST'])
def verificar_credito_rg():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()

    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'  # proteção extra

    custo_rg = 40 if tipo == 'usuario' else 20
    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo_rg:
        flash(f"Você não possui créditos suficientes para gerar RG. Cada RG custa R${custo_rg}. Seu saldo: R${saldo}.", "erro")
        return redirect('/dashboard')

    usuarios[usuario]['creditos'] -= custo_rg
    salvar_usuarios(usuarios)

    return redirect('/formulario_rg')

#########################################################################################################################################################################

@app.route('/verificar_credito_comprovante', methods=['POST'])
def verificar_credito_comprovante():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()
    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'

    custo = 20 if tipo in ['admin', 'gerente', 'revendedor'] else 40
    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo:
        flash(f"Você não possui créditos suficientes para gerar um comprovante. Custa R${custo}. Seu saldo: R${saldo}.", "erro")
        return redirect('/dashboard')

    return redirect('/formulario_comprovante_saopaulo')


@app.route('/visualizar_comprovante')
def visualizar_comprovante():
    usuario = request.args.get('usuario')
    arquivo = request.args.get('arquivo')
    return render_template('visualizar_comprovante.html', usuario=usuario, arquivo=arquivo)



@app.route('/arquivo_comprovante/<usuario>/<arquivo>')
def arquivo_comprovante_usuario(usuario, arquivo):
    caminho = os.path.join(app.root_path, 'static', 'comprovante', usuario, arquivo)
    return send_file(caminho)

@app.route('/formulario_comprovante_saopaulo')
def formulario_comprovante_saopaulo():
    return render_template('formulario_comprovante_saopaulo.html')



@app.route('/formulario_comprovante')
def formulario_comprovante():
    return render_template('formulario_comprovante_saopaulo.html')

def mascarar_cpf(cpf):
    cpf = cpf.replace('.', '').replace('-', '')
    if len(cpf) == 11:
        return f"{cpf[0]}**.***.***-{cpf[-2:]}"
    return cpf  # retorna como está se não tiver 11 dígitos

def formatar_data_brasileira(data_str):
    try:
        data = datetime.strptime(data_str, "%Y-%m-%d")
        return data.strftime("%d/%m/%Y")
    except:
        return data_str  # retorna como está se não conseguir converter

def formatar_mes_ano(data_str):
    try:
        data = datetime.strptime(data_str, "%Y-%m")
        return data.strftime("%m/%Y")
    except:
        return data_str


@app.route('/gerar_documento', methods=['POST'])
def gerar_documento():



    dados = request.form

    # Captura da data de vencimento
    data_vencimento = dados.get('vencimento', '')
    if not data_vencimento:
        data_base = datetime.today()
    else:
        data_base = datetime.strptime(data_vencimento, "%Y-%m-%d")

    # Geração dos últimos 13 meses
    meses_ano = []
    for i in range(13):
        data_ref = data_base - relativedelta(months=i)
        mes_ano = data_ref.strftime("%b/%y").upper()  # ex: SET/23
        meses_ano.append(mes_ano)





    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()

    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()
    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'

    custo_documento = 40 if tipo == 'usuario' else 20
    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo_documento:
        flash(f"Créditos insuficientes. Cada documento custa R${custo_documento}. Seu saldo: R${saldo}.", "erro")
        return render_template('formulario_comprovante_saopaulo.html')

    usuarios[usuario]['creditos'] -= custo_documento
    salvar_usuarios(usuarios)

    dados = request.form.to_dict()
    cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
    nome_arquivo = f"comprovante_{cpf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    # 🔹 Criar pasta do usuário dentro de static/comprovante/
    pasta_usuario = os.path.join(app.root_path, 'static', 'comprovante', usuario)
    os.makedirs(pasta_usuario, exist_ok=True)
    caminho_pdf = os.path.join(pasta_usuario, nome_arquivo)

    mes_ano = formatar_mes_ano(dados.get('mes_ano'))
    vencimento = formatar_data_brasileira(dados.get('vencimento'))
    leitura_anterior = formatar_data_brasileira(dados.get('leitura_anterior'))
    leitura_atual = formatar_data_brasileira(dados.get('leitura_atual'))
    proxima_leitura = formatar_data_brasileira(dados.get('proxima_leitura'))
    data_emissao = formatar_data_brasileira(dados.get('data_emissao'))
    cfop = dados.get('cfop', '')
    codigo_individual = dados.get('codigo_individual', '')
    cpf_mascarado = mascarar_cpf(dados.get('cpf'))
    numero_controle = dados.get('numero_controle', '')


    # 🔹 Gerar PDF com ReportLab
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    c.drawImage("static/base_COMPSAOPAOLO1.png", 0, 0, width=A4[0], height=A4[1])
    c.setFont("Helvetica", 7)

    c.drawString(450, 810, f"Nº {codigo_individual} (PÁGINA 1/2)")
    # Página 1
    c.setFont("Helvetica", 5)
    c.drawString(44, 730, f"{dados.get('nome')}")
    c.drawString(44, 723, f"{dados.get('endereco')}")
    c.drawString(45, 716, f"CEP: {dados.get('cep')} - {dados.get('bairro_sigla_cidade')}")
    c.drawString(45, 709, f"CPF: {cpf_mascarado} INSC. EST: ISENTO")
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(57, 660, f"{mes_ano}")
    c.drawString(116, 660, f"{vencimento}")
    c.drawString(213, 715, f"{dados.get('unidade_consumidora')}")
    c.drawString(214, 687,f"{dados.get('numero_cliente')}")

    c.setFont("Helvetica-Bold", 7)
    c.drawString(325, 753,f"{leitura_anterior}")
    c.drawString(390, 753,f"{leitura_atual}")
    c.drawString(455, 753, f"{dados.get('numero_dias')}")
    c.drawString(495, 753, f"{proxima_leitura}")
    
    c.setFont("Helvetica-Bold", 8)
    c.drawString(282, 711,f"{dados.get('numero_nota_fiscal')}")
    c.drawString(282, 701, f"NOTA FISCAL Nº{dados.get('nota_fiscal')} - SÉRIE B")
    c.drawString(282, 691, f"DATA DE EMISSÃO: {data_emissao}")
    c.setFont("Helvetica", 8)
    c.drawString(282, 681, f"CFOP: {cfop}")
    c.drawString(282, 671, f"CPF/CNPJ: {cpf_mascarado} INSC. EST: ISENTO")

    c.setFont("Helvetica", 7)
    c.drawString(48, 90, f"{dados.get('nome')} - CPF: {cpf_mascarado}")
    c.drawString(48, 82, f"{dados.get('endereco')} - {dados.get('bairro_sigla_cidade')} - CEP: {dados.get('cep')}")
    
    c.drawString(50, 64, f"{data_emissao}")
    c.drawString(235, 64,  f"{mes_ano}")
    c.drawString(333, 64, f"{vencimento}")
    c.drawString(49, 44,f"{numero_controle}")
    c.drawString(355, 397, f"{dados.get('reservado_fisco')}")
    
    c.setFont("Helvetica", 5)
    c.drawString(280, 175,f"Sua conta não está em débito automático? Cadastre-se em seu banco com o código: {dados.get('debito_automatico')}")

    
        # Criação do PDF
    
    c.setFont("Helvetica", 5)


    meses_ptbr = {
        1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR",
        5: "MAI", 6: "JUN", 7: "JUL", 8: "AGO",
        9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"
    }

    meses_ano = []
    for i in range(13):
        data_ref = data_base - relativedelta(months=i)
        mes = meses_ptbr[data_ref.month]
        ano = str(data_ref.year)[-2:]  # últimos dois dígitos
        meses_ano.append(f"{mes}/{ano}")


    # Título da tabela
    y = 513
 

    # Desenho dos meses um abaixo do outro
    for mes in meses_ano:
        y -= 7
        c.drawString(450, y, mes)
    
    
    

    c.showPage()

    # Página 2
    c.setFont("Helvetica", 6)
    
    c.drawImage("static/base_COMPSAOPAOLO2.png", 0, 0, width=A4[0], height=A4[1])
    c.drawString(47, 476, f"{dados.get('unidade_entrega')}")
    c.drawString(101, 476,  f"{dados.get('sequencia')}")
    c.drawString(142, 476, f"{dados.get('numero_medidor')}")

    c.setFont("Helvetica", 8)
    c.drawString(101, 432, f"{dados.get('nome')}")
    c.drawString(101, 424,f"{dados.get('endereco')}")
    c.drawString(124, 415, f"{dados.get('cep')} -")
    c.drawString(168, 415,  f"{dados.get('bairro_sigla_cidade')}")
    c.drawString(158, 406, f"{dados.get('numero_cliente')}")

    c.drawString(110, 320, f"{data_emissao}")
    c.drawString(170, 320, f"{mes_ano}")
    c.drawString(221, 320, f"{vencimento}")

    c.drawString(433, 834, f"Nº {codigo_individual} (PÁGINA 2/2)")
    
    #c.drawString(100, 655, f"Nº Controle: {dados.get('numero_controle')}")
    #c.drawString(100, 700, f"CFOP: {dados.get('cfop')}")
    c.save()

    return redirect(url_for('visualizar_comprovante', usuario=usuario, arquivo=nome_arquivo))


####################################################################################################################


#@app.route('/gerar_documento_ce', methods=['POST'])
#def gerar_documento_ce():
#    dados = request.form
#
#    # Data base
#    data_vencimento = dados.get('vencimento', '')
#    data_base = datetime.today() if not data_vencimento else datetime.strptime(data_vencimento, "%Y-%m-%d")
#
#    # Verificação de login e créditos
#    if 'usuario' not in session:
#        return redirect('/login')
#
#    usuario = session['usuario']
#    usuarios = carregar_usuarios()
#    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
#    if tipo == 'cliente':
#        tipo = 'usuario'
#
#    custo_documento = 40 if tipo == 'usuario' else 20
#    saldo = usuarios[usuario].get('creditos', 0)
#
#    if saldo < custo_documento:
#        return f"Créditos insuficientes. Cada documento custa R${custo_documento}. Seu saldo: R${saldo}"
#
#    usuarios[usuario]['creditos'] -= custo_documento
#    salvar_usuarios(usuarios)
#
#    # Nome do arquivo
#    cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
#    nome_arquivo = f"comprovante_CE_{cpf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#    pasta_usuario = os.path.join(app.root_path, 'static', 'comprovante', usuario)
#    os.makedirs(pasta_usuario, exist_ok=True)
#    caminho_pdf = os.path.join(pasta_usuario, nome_arquivo)
#
#    # Formatação de datas
#    def formatar_data(data_str):
#        return datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y") if data_str else ""
#
#    def mascarar_cpf(cpf):
#        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf
#
#    mes_ano = datetime.strptime(dados.get('mes_ano'), "%Y-%m").strftime("%m/%Y")
#    vencimento = formatar_data(dados.get('vencimento'))
#    leitura_anterior = formatar_data(dados.get('leitura_anterior'))
#    leitura_atual = formatar_data(dados.get('leitura_atual'))
#    proxima_leitura = formatar_data(dados.get('proxima_leitura'))
#    data_emissao = formatar_data(dados.get('data_emissao'))
#    cpf_mascarado = mascarar_cpf(cpf)
#    numero_controle = dados.get('numero_controle', '')
#
#    
#    # Criar PDF
#    c = canvas.Canvas(caminho_pdf, pagesize=A4)
#    c.drawImage("static/base_COMPCEARA1.png", 0, 0, width=A4[0], height=A4[1])
#    c.setFont("Helvetica", 7)
#
#    c.drawString(450, 810, f"Nº {dados.get('codigo_individual')} (PÁGINA 1/2)")
#    c.setFont("Helvetica", 5)
#    c.drawString(44, 730, f"{dados.get('nome')}")
#    c.drawString(44, 723, f"{dados.get('endereco')}")
#    c.drawString(45, 716, f"CEP: {dados.get('cep')} - {dados.get('bairro_sigla_cidade')}")
#    c.drawString(45, 709, f"CPF: {cpf_mascarado} INSC. EST: ISENTO")
#
#    c.setFont("Helvetica-Bold", 9)
#    c.drawString(57, 660, f"{mes_ano}")
#    c.drawString(116, 660, f"{vencimento}")
#    c.drawString(213, 715, f"{dados.get('unidade_consumidora')}")
#    c.drawString(214, 687, f"{dados.get('numero_cliente')}")
#
#    c.setFont("Helvetica-Bold", 7)
#    c.drawString(325, 753, f"{leitura_anterior}")
#    c.drawString(390, 753, f"{leitura_atual}")
#    c.drawString(455, 753, f"{dados.get('numero_dias')}")
#    c.drawString(495, 753, f"{proxima_leitura}")
#
#    c.setFont("Helvetica", 5)
#    c.drawString(459, 690, f"{data_emissao}")
#    c.drawString(353, 683, f"CFOP: {dados.get('cfop')}")
#    
#
#
#
#
#
#
#    c.setFont("Helvetica", 7)
#    c.drawString(48, 90, f"{dados.get('nome')} - CPF: {cpf_mascarado} ")
#    c.drawString(48, 82, f"{dados.get('endereco')} - {dados.get('bairro_sigla_cidade')} - CEP: {dados.get('cep')} ")
#    
#    c.drawString(50, 64, f"{data_emissao}")
#    c.drawString(142, 64,f"020{numero_controle}27") #notafiscal adult
#    c.drawString(235, 64,  f"{mes_ano}")
#    c.drawString(333, 64, f"{vencimento}")
#    c.drawString(49, 48,f"{numero_controle}")
#    c.drawString(355, 397, f"{dados.get('reservado_fisco')}")
#    c.setFont("Helvetica", 8)
#    c.drawString(433, 64, f"183,17")
#
#    c.setFont("Helvetica", 5)
#    c.drawString(280, 175, f"Sua conta não está em débito automático? Cadastre-se com o código: {dados.get('debito_automatico')}")
#
#    # Coluna de meses
#    meses_ptbr = {
#        1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR",
#        5: "MAI", 6: "JUN", 7: "JUL", 8: "AGO",
#        9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"
#    }
#    y = 513
#    for i in range(13):
#        data_ref = data_base - relativedelta(months=i)
#        mes = meses_ptbr[data_ref.month]
#        ano = str(data_ref.year)[-2:]
#        y -= 7
#        c.drawString(450, y, f"{mes}/{ano}")
#
#    c.showPage()
#
#    # Página 2
#    c.setFont("Helvetica", 6)
#    c.drawImage("static/base_COMPCEARA2.png", 0, 0, width=A4[0], height=A4[1])
#    c.drawString(47, 476, f"{dados.get('unidade_entrega')}")
#    c.drawString(101, 476, f"{dados.get('sequencia')}")
#    c.drawString(130, 476, f"{dados.get('numero_medidor')}")
#
#    c.setFont("Helvetica", 8)
#    c.drawString(102, 433, f"{dados.get('nome')}")
#    c.drawString(102, 420, f"{dados.get('endereco')}")
#    c.drawString(102, 408, f"{dados.get('bairro_sigla_cidade')}")
#    c.drawString(103, 398, f"CEP: {dados.get('cep')}")
#    c.drawString(103, 388, f"CPF/CNPJ:  {cpf_mascarado} INSC. EST: ISENTO")
#    
#    c.drawString(105, 368, f"{dados.get('unidade_entrega')}  {dados.get('sequencia')} ")
#    
#    c.drawString(103, 354,f"{dados.get('numero_cliente')}")
#
#    
#
#    c.drawString(110, 320, f"{data_emissao}")
#    c.drawString(170, 320, f"{mes_ano}")
#    c.drawString(221, 320, f"{vencimento}")
#    c.drawString(433, 834, f"Nº {dados.get('codigo_individual')} (PÁGINA 2/2)")
#
#    c.save()
#
#    return redirect(url_for('visualizar_comprovante', usuario=usuario, arquivo=nome_arquivo))


@app.route('/estado/<sigla>')
def redirecionar_estado(sigla):
    sigla = sigla.upper()

    if sigla == 'CE':
        return redirect('/formulario_comprovante_ceara')
    elif sigla == 'SP':
        return redirect('/formulario_comprovante_saopaulo')
    elif sigla == 'MG':
        return redirect('/formulario_comprovante_mg')
    else:
        flash(f"Formulário para o estado {sigla} ainda não está disponível.", "erro")
        return redirect('/dashboard')

@app.route('/formulario_comprovante_ceara')
def formulario_comprovante_ceara():
    return render_template('formulario_comprovante_ceara.html')


@app.route('/formulario_comprovante_mg')
def formulario_comprovante_mg():
    return render_template('formulario_comprovante_mg.html')



@app.route('/gerar_documento_ce', methods=['POST'])
def gerar_documento_ce():
    dados = request.form

    # Data base
    data_vencimento = dados.get('vencimento', '')
    data_base = datetime.today() if not data_vencimento else datetime.strptime(data_vencimento, "%Y-%m-%d")

    # Verificação de login e créditos
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()
    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'

    custo_documento = 40 if tipo == 'usuario' else 20
    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo_documento:
        flash(f"Créditos insuficientes. Cada documento custa R${custo_documento}. Seu saldo: R${saldo}.", "erro")
        return render_template('formulario_comprovante_ceara.html')

    usuarios[usuario]['creditos'] -= custo_documento
    salvar_usuarios(usuarios)

    # Nome do arquivo
    cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
    nome_arquivo = f"comprovante_CE_{cpf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pasta_usuario = os.path.join(app.root_path, 'static', 'comprovante', usuario)
    os.makedirs(pasta_usuario, exist_ok=True)
    caminho_pdf = os.path.join(pasta_usuario, nome_arquivo)

    # Formatação de datas
    def formatar_data(data_str):
        return datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y") if data_str else ""

    def mascarar_cpf(cpf):
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf

    mes_ano = datetime.strptime(dados.get('mes_ano'), "%Y-%m").strftime("%m/%Y")
    vencimento = formatar_data(dados.get('vencimento'))
    leitura_anterior = formatar_data(dados.get('leitura_anterior'))
    leitura_atual = formatar_data(dados.get('leitura_atual'))
    proxima_leitura = formatar_data(dados.get('proxima_leitura'))
    data_emissao = formatar_data(dados.get('data_emissao'))
    cpf_mascarado = mascarar_cpf(cpf)
    numero_controle = dados.get('numero_controle', '')

    # Criar PDF
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    c.drawImage("static/base_COMPCEARA1.png", 0, 0, width=A4[0], height=A4[1])
    c.setFont("Helvetica", 7)

    c.drawString(450, 810, f"Nº {dados.get('codigo_individual')} (PÁGINA 1/2)")
    c.setFont("Helvetica", 5)
    c.drawString(44, 730, f"{dados.get('nome')}")
    c.drawString(44, 723, f"{dados.get('endereco')}")
    c.drawString(45, 716, f"CEP: {dados.get('cep')} - {dados.get('bairro_sigla_cidade')}")
    c.drawString(45, 709, f"CPF: {cpf_mascarado} INSC. EST: ISENTO")

    c.setFont("Helvetica-Bold", 9)
    c.drawString(57, 660, f"{mes_ano}")
    c.drawString(116, 660, f"{vencimento}")
    c.drawString(213, 715, f"{dados.get('unidade_consumidora')}")
    c.drawString(214, 687, f"{dados.get('numero_cliente')}")

    c.setFont("Helvetica-Bold", 7)
    c.drawString(325, 753, f"{leitura_anterior}")
    c.drawString(390, 753, f"{leitura_atual}")
    c.drawString(455, 753, f"{dados.get('numero_dias')}")
    c.drawString(495, 753, f"{proxima_leitura}")

    c.setFont("Helvetica", 5)
    c.drawString(459, 690, f"{data_emissao}")
    c.drawString(353, 683, f"CFOP: {dados.get('cfop')}")

    c.setFont("Helvetica", 7)
    c.drawString(48, 90, f"{dados.get('nome')} - CPF: {cpf_mascarado} ")
    c.drawString(48, 82, f"{dados.get('endereco')} - {dados.get('bairro_sigla_cidade')} - CEP: {dados.get('cep')} ")

    c.drawString(50, 64, f"{data_emissao}")
    c.drawString(142, 64, f"020{numero_controle}27")
    c.drawString(235, 64, f"{mes_ano}")
    c.drawString(333, 64, f"{vencimento}")
    c.drawString(49, 48, f"{numero_controle}")
    c.drawString(355, 397, f"{dados.get('reservado_fisco')}")
    c.setFont("Helvetica", 8)
    c.drawString(433, 64, f"183,17")

    c.setFont("Helvetica", 5)
    c.drawString(280, 175, f"Sua conta não está em débito automático? Cadastre-se com o código: {dados.get('debito_automatico')}")

    meses_ptbr = {
        1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR",
        5: "MAI", 6: "JUN", 7: "JUL", 8: "AGO",
        9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"
    }
    y = 513
    for i in range(13):
        data_ref = data_base - relativedelta(months=i)
        mes = meses_ptbr[data_ref.month]
        ano = str(data_ref.year)[-2:]
        y -= 7
        c.drawString(450, y, f"{mes}/{ano}")

    c.showPage()

    c.setFont("Helvetica", 6)
    c.drawImage("static/base_COMPCEARA2.png", 0, 0, width=A4[0], height=A4[1])
    c.drawString(47, 476, f"{dados.get('unidade_entrega')}")
    c.drawString(101, 476, f"{dados.get('sequencia')}")
    c.drawString(130, 476, f"{dados.get('numero_medidor')}")

    c.setFont("Helvetica", 8)
    c.drawString(102, 433, f"{dados.get('nome')}")
    c.drawString(102, 420, f"{dados.get('endereco')}")
    c.drawString(102, 408, f"{dados.get('bairro_sigla_cidade')}")
    c.drawString(103, 398, f"CEP: {dados.get('cep')}")
    c.drawString(103, 388, f"CPF/CNPJ:  {cpf_mascarado} INSC. EST: ISENTO")

    c.drawString(105, 368, f"{dados.get('unidade_entrega')}  {dados.get('sequencia')} ")
    c.drawString(103, 354, f"{dados.get('numero_cliente')}")

    c.drawString(110, 320, f"{data_emissao}")
    c.drawString(170, 320, f"{mes_ano}")
    c.drawString(221, 320, f"{vencimento}")
    c.drawString(433, 834, f"Nº {dados.get('codigo_individual')} (PÁGINA 2/2)")

    c.save()

    return redirect(url_for('visualizar_comprovante', usuario=usuario, arquivo=nome_arquivo))





# Rota genérica para redirecionar por estado
@app.route('/estado/<sigla>')
def formulario_por_estado(sigla):
    if sigla == "CE":
        return render_template("formulario_comprovante_ceara.html")
    elif sigla == "SP":
        return render_template("formulario_comprovante_sao_paulo.html")
    else:
        return f"Formulário para o estado {sigla} ainda não está disponível."

@app.route('/comprovantes_salvos')
def comprovantes_salvos():
    usuario = session.get('usuario')
    if not usuario:
        return redirect('/login')

    pasta_usuario = os.path.join(app.root_path, 'static', 'comprovante', usuario)
    arquivos = os.listdir(pasta_usuario) if os.path.exists(pasta_usuario) else []

    comprovantes = []
    for nome in arquivos:
        partes = nome.split('_')
        cpf = partes[2] if len(partes) > 2 else ''
        data_emissao = nome.split('_')[-1].replace('.pdf', '')
        comprovantes.append({
            'nome': partes[1] if len(partes) > 1 else 'Desconhecido',
            'cpf': cpf,
            'data_emissao': data_emissao,
            'arquivo': nome
        })

    return render_template('ver_comp_salvos.html', comprovantes=comprovantes, usuario=usuario)

@app.route('/baixar_comprovante/<usuario>/<arquivo>')
def baixar_comprovante(usuario, arquivo):
    pasta = os.path.join(app.root_path, 'static', 'comprovante', usuario)
    caminho = os.path.join(pasta, arquivo)

    if os.path.exists(caminho):
        return send_file(caminho, as_attachment=True)
    else:
        flash("Arquivo não encontrado.", "erro")
        return redirect(url_for('comprovantes_salvos'))
    
@app.route('/excluir_comprovante/<usuario>/<arquivo>', methods=['POST'])
def excluir_comprovante(usuario, arquivo):
    pasta = os.path.join(app.root_path, 'static', 'comprovante', usuario)
    caminho = os.path.join(pasta, arquivo)

    if os.path.exists(caminho):
        os.remove(caminho)
        flash("Comprovante excluído com sucesso.", "sucesso")
    else:
        flash("Arquivo não encontrado para exclusão.", "erro")

    return redirect(url_for('comprovantes_salvos'))



####################################################################################################################################################


@app.route('/gerar_documento_mg', methods=['POST'])
def gerar_documento_mg():
    dados = request.form

    # Data base
    data_vencimento = dados.get('vencimento', '')
    data_base = datetime.today() if not data_vencimento else datetime.strptime(data_vencimento, "%Y-%m-%d")

    # Verificação de login e créditos
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    usuarios = carregar_usuarios()
    tipo = usuarios[usuario].get('tipo', 'usuario').lower()
    if tipo == 'cliente':
        tipo = 'usuario'

    custo_documento = 40 if tipo == 'usuario' else 20
    saldo = usuarios[usuario].get('creditos', 0)

    if saldo < custo_documento:
        flash(f"Créditos insuficientes. Cada documento custa R${custo_documento}. Seu saldo: R${saldo}.", "erro")
        return render_template('formulario_comprovante_mg.html')

    usuarios[usuario]['creditos'] -= custo_documento
    salvar_usuarios(usuarios)

    # Nome do arquivo
    cpf = dados.get('cpf', '').replace('.', '').replace('-', '')
    nome_arquivo = f"comprovante_MG_{cpf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pasta_usuario = os.path.join(app.root_path, 'static', 'comprovante', usuario)
    os.makedirs(pasta_usuario, exist_ok=True)
    caminho_pdf = os.path.join(pasta_usuario, nome_arquivo)

    # Formatação de datas
    def formatar_data(data_str):
        return datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y") if data_str else ""

    def mascarar_cpf(cpf):
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf



 
    def gerar_codigo_barras():
        partes = [
            str(random.randint(80000000000, 89999999999)) + "-" + str(random.randint(0, 9)),
            str(random.randint(70000000000, 79999999999)) + "-" + str(random.randint(0, 9)),
            str(random.randint(500000000000, 599999999999)) + "-" + str(random.randint(0, 9)),
            str(random.randint(80000000000, 89999999999)) + "-" + str(random.randint(0, 9))
        ]
        return " ".join(partes)
   

    data_mes_ano = datetime.strptime(dados.get('mes_ano'), "%Y-%m")
    meses_extenso = [
        "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
        "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
    ]
    mes_ano = f"{meses_extenso[data_mes_ano.month - 1]}/{data_mes_ano.year}"

    



    
    vencimento = formatar_data(dados.get('vencimento'))
    leitura_anterior = formatar_data_dia_mes(dados.get('leitura_anterior'))
    leitura_atual = formatar_data_dia_mes(dados.get('leitura_atual'))
    proxima_leitura = formatar_data_dia_mes(dados.get('proxima_leitura'))
    data_emissao = formatar_data(dados.get('data_emissao'))
    cpf_mascarado = mascarar_cpf(cpf)
    numero_controle = dados.get('numero_controle', '')
    dados.get('endereco')
    dados.get('bairro')
    codigo_barras = gerar_codigo_barras()
    mes_ano = f"{meses_extenso[data_mes_ano.month - 1]}/{data_mes_ano.year}"





    # Criar PDF
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    c.drawImage("static/base_COMPMG1.png", 0, 0, width=A4[0], height=A4[1])

    

    
    c.setFont("Helvetica-Bold", 8)
    c.drawString(13, 773, f"{dados.get('nome')}")
    c.setFont("Helvetica", 8)
    c.drawString(13, 763, f"{dados.get('endereco')}")
    c.drawString(15, 753, f"{dados.get('bairro')}")
    c.drawString(15, 744, f"CEP: {dados.get('cep')} - {dados.get('bairro_sigla_cidade')}")
    c.drawString(15, 734, f"CPF: {cpf_mascarado}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(333, 760,f"{dados.get('numero_cliente')}")
    c.drawString(305, 731, f"{mes_ano}")
    c.drawString(413, 731, f"{vencimento}")
    c.drawString(480, 760, f"{dados.get('unidade_consumidora')}")

    c.setFont("Helvetica", 7)
    c.drawString(115, 635, f"APJ{dados.get('cfop')}") #medição APJ
    

    c.setFont("Helvetica", 10)
    c.drawString(348, 670, f"{leitura_anterior}")
    c.drawString(399, 670, f"{leitura_atual}")
    c.drawString(445, 670, f"{proxima_leitura}")
    c.drawString(515, 678, f"{data_emissao}")



    c.setFont("Helvetica-Bold", 11)
    c.drawString(139, 58, f"{dados.get('debito_automatico')}")
    c.drawString(262, 58, f"{numero_controle}")
    c.drawString(362, 58,  f"{vencimento}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(130, 42,  f"{codigo_barras}")
    c.drawString(475, 42, f"{mes_ano}")



   
    c.setFont("Helvetica",6 )
    meses_ptbr = {
        1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR",
        5: "MAI", 6: "JUN", 7: "JUL", 8: "AGO",
        9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"
    }
    y = 244
    for i in range(13):
        data_ref = data_base - relativedelta(months=i)
        mes = meses_ptbr[data_ref.month]
        ano = str(data_ref.year)[-2:]
        y -= 10.5
        c.drawString(13, y, f"{mes}/{ano}")

    c.showPage()

    c.save()

    return redirect(url_for('visualizar_comprovante', usuario=usuario, arquivo=nome_arquivo))


def formatar_data_dia_mes(data_str):
    if data_str:
        try:
            return datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m")
        except ValueError:
            return ""
    return ""




############ FIM

#if __name__ == '__main__':
 #   app.run(debug=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
