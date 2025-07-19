from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time

app = Flask(__name__, template_folder='templates')
# A 'secret_key' é necessária para a sessão do SocketIO
app.config['SECRET_KEY'] = 'bests-ia-secret-key!'
# Integra o SocketIO com o aplicativo Flask
socketio = SocketIO(app, async_mode='eventlet')

def automation_engine(sid, data):
    """
    O motor de automação que agora envia atualizações em tempo real via WebSockets.
    'sid' é o ID da sessão do usuário conectado.
    'data' contém as credenciais (ra, digito, uf, senha).
    """
    def log(message):
        """Função auxiliar para emitir logs para o cliente correto."""
        print(f"LOG para {sid}: {message}")
        socketio.emit('new_log', {'message': message}, room=sid)
        time.sleep(0.5) # Pequena pausa para o usuário conseguir ler

    log("▶️ Bests.IA ativado. Iniciando conexão segura...")
    
    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            log("🌍 Navegando para o portal Sala do Futuro...")
            page.goto("https://saladofuturo.educacao.sp.gov.br/login-alunos", timeout=60000)
            
            log("✍️ Preenchendo credenciais...")
            page.wait_for_selector("#ra-aluno", timeout=15000)
            page.fill("#ra-aluno", data['ra'])
            page.fill("#digito-ra-aluno", data['digito'])
            page.click("#uf-ra-aluno")
            page.click(f"//li[contains(text(), '{data['uf'].upper()}')]")
            page.fill("#senha-aluno", data['senha'])
            
            log("🔑 Autenticando...")
            page.click("#btn-acessar-aluno")
            
            log("🕵️ Verificando identidade...")
            welcome_element = page.wait_for_selector("//*[contains(text(), 'Olá,')]", timeout=20000)
            full_text = welcome_element.inner_text()
            nome_aluno = full_text.split(',')[1].strip().split(' ')[0].capitalize()
            
            log(f"✅ Identidade confirmada: {nome_aluno}")
            socketio.emit('login_success', {'name': nome_aluno}, room=sid)

        except PlaywrightTimeoutError:
            log("❌ Falha na autenticação. Verifique os dados ou o site pode estar offline.")
            socketio.emit('automation_error', {'message': 'Tempo de espera esgotado.'}, room=sid)
        except Exception as e:
            log(f"❌ Erro inesperado: {str(e)}")
            socketio.emit('automation_error', {'message': str(e)}, room=sid)
        finally:
            if browser:
                browser.close()
            log("🔌 Conexão finalizada.")

@app.route('/')
def index():
    """Serve a página principal do site."""
    return render_template('index.html')

@socketio.on('start_automation')
def handle_start_automation(data):
    """
    Este evento é chamado quando o usuário clica no botão no site.
    Ele inicia o motor de automação em uma nova thread para não travar o servidor.
    """
    sid = request.sid # Pega o ID da sessão do usuário
    print(f"Automação solicitada pelo cliente: {sid}")
    # Inicia a automação em background
    socketio.start_background_task(target=automation_engine, sid=sid, data=data)

if __name__ == '__main__':
    # Este modo é usado para testes locais
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)
          
