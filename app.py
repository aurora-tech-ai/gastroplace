from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
import json
import os
from functools import wraps
import secrets
import hashlib
from threading import Lock

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
CORS(app)

# Configurar Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'YOUR_API_KEY_HERE')
genai.configure(api_key=GEMINI_API_KEY)

# Inicializar modelo Gemini
model = genai.GenerativeModel('gemini-2.5-pro')

# Credenciais do admin (em produção, use hash seguro e banco de dados)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

# Paths dos arquivos JSON
MENU_FILE = 'menu.json'
ORDERS_FILE = 'orders.json'
RESTAURANT_FILE = 'restaurant.json'

# Lock para operações de arquivo
file_lock = Lock()

# Sessões de chat em memória
chat_sessions = {}

def initialize_files():
    """Cria os arquivos JSON iniciais se não existirem"""
    
    # Menu inicial
    default_menu = {
        "pratos_principais": [
            {
                "id": 1,
                "nome": "Filé à Parmegiana",
                "preco": 89.90,
                "descricao": "Serve 2 pessoas",
                "categoria": "pratos_principais",
                "ativo": True,
                "imagem": ""
            },
            {
                "id": 2,
                "nome": "Salmão Grelhado",
                "preco": 95.00,
                "descricao": "Com legumes grelhados",
                "categoria": "pratos_principais",
                "ativo": True,
                "imagem": ""
            },
            {
                "id": 3,
                "nome": "Risoto de Camarão",
                "preco": 85.00,
                "descricao": "Cremoso e saboroso",
                "categoria": "pratos_principais",
                "ativo": True,
                "imagem": ""
            }
        ],
        "entradas": [
            {
                "id": 4,
                "nome": "Carpaccio",
                "preco": 45.00,
                "descricao": "Fino e temperado",
                "categoria": "entradas",
                "ativo": True,
                "imagem": ""
            },
            {
                "id": 5,
                "nome": "Bruschetta",
                "preco": 35.00,
                "descricao": "6 unidades",
                "categoria": "entradas",
                "ativo": True,
                "imagem": ""
            }
        ],
        "sobremesas": [
            {
                "id": 6,
                "nome": "Tiramisù",
                "preco": 28.00,
                "descricao": "Tradicional italiano",
                "categoria": "sobremesas",
                "ativo": True,
                "imagem": ""
            },
            {
                "id": 7,
                "nome": "Petit Gateau",
                "preco": 32.00,
                "descricao": "Com sorvete de creme",
                "categoria": "sobremesas",
                "ativo": True,
                "imagem": ""
            }
        ],
        "bebidas": [
            {
                "id": 8,
                "nome": "Refrigerantes",
                "preco": 8.00,
                "descricao": "Coca, Guaraná, Sprite",
                "categoria": "bebidas",
                "ativo": True,
                "imagem": ""
            },
            {
                "id": 9,
                "nome": "Sucos Naturais",
                "preco": 12.00,
                "descricao": "Laranja, Limão, Maracujá",
                "categoria": "bebidas",
                "ativo": True,
                "imagem": ""
            }
        ]
    }
    
    # Informações do restaurante
    default_restaurant = {
        "nome": "GastroPlace",
        "telefone": "(11) 1234-5678",
        "endereco": "Rua Exemplo, 123 - São Paulo/SP",
        "horario_funcionamento": {
            "segunda": "Fechado",
            "terca": "11:00 - 23:00",
            "quarta": "11:00 - 23:00",
            "quinta": "11:00 - 23:00",
            "sexta": "11:00 - 23:00",
            "sabado": "11:00 - 23:00",
            "domingo": "11:00 - 23:00"
        },
        "delivery": {
            "ativo": True,
            "taxa_entrega": 8.00,
            "tempo_minimo": 30,
            "tempo_maximo": 50,
            "raio_km": 10,
            "pedido_minimo": 30.00
        },
        "pagamento": {
            "dinheiro": True,
            "cartao_credito": True,
            "cartao_debito": True,
            "pix": True,
            "vale_refeicao": True
        },
        "redes_sociais": {
            "whatsapp": "(11) 91234-5678",
            "instagram": "@gastroplacesp",
            "facebook": "gastroplacesp"
        }
    }
    
    # Criar arquivos se não existirem
    if not os.path.exists(MENU_FILE):
        save_json(MENU_FILE, default_menu)
        print(f"✅ Arquivo {MENU_FILE} criado com sucesso!")
    
    if not os.path.exists(RESTAURANT_FILE):
        save_json(RESTAURANT_FILE, default_restaurant)
        print(f"✅ Arquivo {RESTAURANT_FILE} criado com sucesso!")
    
    if not os.path.exists(ORDERS_FILE):
        save_json(ORDERS_FILE, [])
        print(f"✅ Arquivo {ORDERS_FILE} criado com sucesso!")

def load_json(filename):
    """Carrega dados de um arquivo JSON com tratamento de erro"""
    with file_lock:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"📖 Lendo {filename}: {len(data) if isinstance(data, list) else 'objeto'} items")
                return data
        except FileNotFoundError:
            print(f"⚠️  Arquivo {filename} não encontrado, retornando estrutura vazia")
            return {} if filename != ORDERS_FILE else []
        except json.JSONDecodeError:
            print(f"❌ Erro ao decodificar {filename}, retornando estrutura vazia")
            return {} if filename != ORDERS_FILE else []

def save_json(filename, data):
    """Salva dados em um arquivo JSON com verificação"""
    with file_lock:
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"💾 Salvando {filename}: {len(data) if isinstance(data, list) else 'objeto'} items")
        except Exception as e:
            print(f"❌ Erro ao salvar {filename}: {str(e)}")

def get_active_menu_items():
    """Retorna apenas os itens ativos do menu"""
    menu = load_json(MENU_FILE)
    active_items = []
    
    for category, items in menu.items():
        for item in items:
            if item.get('ativo', True):
                active_items.append(item)
    
    return active_items

def generate_restaurant_context():
    """Gera o contexto do restaurante baseado nos JSONs"""
    restaurant = load_json(RESTAURANT_FILE)
    menu = load_json(MENU_FILE)
    
    # Construir string do cardápio
    menu_str = ""
    for category_name, items in menu.items():
        active_items = [item for item in items if item.get('ativo', True)]
        if active_items:
            category_titles = {
                'pratos_principais': '🍝 PRATOS PRINCIPAIS',
                'entradas': '🥗 ENTRADAS',
                'sobremesas': '🍰 SOBREMESAS',
                'bebidas': '🥤 BEBIDAS'
            }
            menu_str += f"\n{category_titles.get(category_name, category_name.upper())}:\n"
            for item in active_items:
                menu_str += f"- {item['nome']}: R$ {item['preco']:.2f} ({item['descricao']})\n"
    
    # Construir horários
    horarios = restaurant.get('horario_funcionamento', {})
    horarios_str = ", ".join([f"{dia.capitalize()}: {horario}" for dia, horario in horarios.items()])
    
    # Construir formas de pagamento
    pagamentos = restaurant.get('pagamento', {})
    formas_pagamento = [forma.replace('_', ' ').title() for forma, ativo in pagamentos.items() if ativo]
    
    context = f"""
Você é um assistente virtual do {restaurant['nome']}, um restaurante sofisticado e acolhedor.

INFORMAÇÕES DO RESTAURANTE (use estas informações exatas):
{json.dumps(restaurant, indent=2, ensure_ascii=False)}

CARDÁPIO COMPLETO (use APENAS estes itens):
{json.dumps(menu, indent=2, ensure_ascii=False)}

REGRAS CRÍTICAS:
1. Use APENAS os itens do cardápio JSON acima que têm "ativo": true
2. NUNCA invente pratos ou bebidas que não estão no JSON
3. Use EXATAMENTE os nomes e preços do JSON
4. Se alguém pedir algo não listado, diga educadamente que não está disponível
5. Para delivery, sempre adicione a taxa de entrega de R$ {restaurant['delivery']['taxa_entrega']:.2f}
6. Tempo de entrega: {restaurant['delivery']['tempo_minimo']}-{restaurant['delivery']['tempo_maximo']} minutos
7. Pedido mínimo para delivery: R$ {restaurant['delivery']['pedido_minimo']:.2f}

FORMAS DE PAGAMENTO ACEITAS: {', '.join(formas_pagamento)}

PROCESSO DE PEDIDO:
1. Anote os itens que o cliente deseja
2. Solicite o nome do cliente
3. Solicite o telefone para contato (IMPORTANTE!)
4. Pergunte se é delivery ou retirada
5. Se delivery, solicite o endereço completo
6. Informe as formas de pagamento aceitas e pergunte qual prefere
7. Apresente o resumo completo com valores
8. IMPORTANTE: Após o cliente CONFIRMAR o pedido, sempre termine sua resposta com:
   "PEDIDO CONFIRMADO COM SUCESSO! Número do pedido: [será gerado automaticamente]"

Seja sempre cordial e profissional. Use as informações dos JSONs acima como fonte única de verdade.
"""
    
    return context

def extract_order_info(conversation):
    """Extrai informações do pedido validando contra o menu JSON"""
    menu = load_json(MENU_FILE)
    restaurant = load_json(RESTAURANT_FILE)
    
    # Verificar se há confirmação de pedido na conversa
    if "PEDIDO CONFIRMADO COM SUCESSO!" not in conversation:
        print("❌ Conversa não contém confirmação de pedido")
        return None
    
    # Criar lista de itens válidos
    valid_items = []
    for category, items in menu.items():
        for item in items:
            if item.get('ativo', True):
                valid_items.append(item)
    
    prompt = f"""
    Analise esta conversa de pedido já CONFIRMADO e extraia as informações em JSON.
    
    Conversa: {conversation}
    
    Extraia as seguintes informações que foram mencionadas na conversa:
    - Itens pedidos (procure por nomes do cardápio)
    - Nome do cliente
    - Se é delivery ou retirada
    - Endereço (se for delivery)
    - Forma de pagamento
    - Valores mencionados
    
    Retorne no formato:
    {{
        "items": [
            {{"id": 1, "nome": "Nome do Item", "quantidade": 1, "preco_unitario": 0.00}}
        ],
        "cliente": "Nome do Cliente",
        "tipo_entrega": "delivery",
        "endereco": "Endereço completo",
        "forma_pagamento": "cartão",
        "subtotal": 0.00,
        "taxa_entrega": 8.00,
        "total": 0.00,
        "observacoes": null
    }}
    
    IMPORTANTE: Esta conversa JÁ TEM um pedido confirmado. Extraia as informações mencionadas.
    
    Cardápio para referência:
    {json.dumps(valid_items, indent=2, ensure_ascii=False)}
    """
    
    try:
        print(f"\n🔍 Extraindo pedido confirmado...")
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Limpar resposta
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        print(f"📝 Resposta do Gemini (primeiros 300 chars): {response_text[:300]}...")
        
        order_data = json.loads(response_text)
        
        if order_data and order_data.get('items'):
            print(f"✅ Pedido extraído: {len(order_data['items'])} itens")
            
            # Validar e corrigir IDs e preços
            for order_item in order_data.get('items', []):
                item_found = False
                # Buscar item por nome (case insensitive)
                for valid_item in valid_items:
                    if valid_item['nome'].lower() in order_item['nome'].lower() or order_item['nome'].lower() in valid_item['nome'].lower():
                        order_item['id'] = valid_item['id']
                        order_item['nome'] = valid_item['nome']
                        order_item['preco_unitario'] = valid_item['preco']
                        item_found = True
                        print(f"   ✓ Item encontrado: {valid_item['nome']} - R$ {valid_item['preco']}")
                        break
                
                if not item_found:
                    print(f"   ⚠️  Item não encontrado no cardápio: {order_item['nome']}")
            
            # Recalcular totais
            subtotal = sum(item['preco_unitario'] * item.get('quantidade', 1) for item in order_data['items'])
            taxa = restaurant['delivery']['taxa_entrega'] if order_data.get('tipo_entrega') == 'delivery' else 0
            order_data['subtotal'] = round(subtotal, 2)
            order_data['taxa_entrega'] = round(taxa, 2)
            order_data['total'] = round(subtotal + taxa, 2)
            
            print(f"💰 Totais: Subtotal R$ {order_data['subtotal']} + Taxa R$ {order_data['taxa_entrega']} = Total R$ {order_data['total']}")
            
            return order_data
            
        else:
            print("❌ Estrutura de pedido inválida ou sem itens")
            return None
        
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao decodificar JSON: {e}")
        print(f"   Resposta: {response_text[:500]}...")
        return None
    except Exception as e:
        print(f"❌ Erro geral: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None

def login_required(f):
    """Decorator para rotas protegidas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def generate_order_id():
    """Gera um ID único para o pedido"""
    return f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"

@app.route('/')
def index():
    """Página principal com o chat"""
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(8)
    return render_template('chat.html')

@app.route('/login')
def login():
    """Página de login"""
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """API de login"""
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH:
        session['admin_logged_in'] = True
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Credenciais inválidas'}), 401

@app.route('/logout')
def logout():
    """Logout"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard administrativo"""
    return render_template('dashboard.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint do chat"""
    data = request.json
    user_message = data.get('message', '')
    session_id = session.get('session_id', 'default')
    
    # Recuperar ou criar histórico da sessão
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    
    # Adicionar mensagem do usuário ao histórico
    chat_sessions[session_id].append(f"Cliente: {user_message}")
    
    # Construir contexto com JSONs atualizados
    conversation_history = "\n".join(chat_sessions[session_id][-10:])
    restaurant_context = generate_restaurant_context()
    
    prompt = f"""
    {restaurant_context}
    
    Histórico da conversa:
    {conversation_history}
    
    Responda com base APENAS nas informações dos JSONs fornecidos.
    
    IMPORTANTE: Se você confirmar um pedido nesta resposta, 
    inclua no final da sua mensagem o seguinte formato EXATO:
    
    ###PEDIDO_CONFIRMADO###
    ITENS: Nome do Item 1 (quantidade), Nome do Item 2 (quantidade)
    CLIENTE: Nome do Cliente
    TELEFONE: (11) 99999-9999
    ENTREGA: delivery ou retirada
    ENDERECO: endereço completo ou "retirada no local"
    PAGAMENTO: forma de pagamento
    ###FIM_PEDIDO###
    """
    
    try:
        # Gerar resposta com Gemini
        response = model.generate_content(prompt)
        bot_response = response.text
        
        # Adicionar resposta ao histórico
        chat_sessions[session_id].append(f"Assistente: {bot_response}")
        
        # Verificar se há pedido confirmado
        order_created = False
        order_id = None
        
        if "###PEDIDO_CONFIRMADO###" in bot_response and "###FIM_PEDIDO###" in bot_response:
            print("\n🎯 Detectado marcador de pedido confirmado!")
            
            # Extrair informações do pedido diretamente da resposta
            try:
                # Extrair seção do pedido
                start = bot_response.find("###PEDIDO_CONFIRMADO###")
                end = bot_response.find("###FIM_PEDIDO###")
                pedido_section = bot_response[start:end]
                
                print(f"📋 Seção do pedido:\n{pedido_section}")
                
                # Parse manual das informações
                lines = pedido_section.split('\n')
                order_data = {
                    'items': [],
                    'cliente': '',
                    'telefone': '',
                    'tipo_entrega': '',
                    'endereco': '',
                    'forma_pagamento': ''
                }
                
                menu = load_json(MENU_FILE)
                restaurant = load_json(RESTAURANT_FILE)
                
                for line in lines:
                    if line.startswith('ITENS:'):
                        # Processar itens
                        items_str = line.replace('ITENS:', '').strip()
                        items_parts = items_str.split(',')
                        
                        for item_part in items_parts:
                            # Extrair nome e quantidade
                            if '(' in item_part and ')' in item_part:
                                nome = item_part[:item_part.find('(')].strip()
                                qty_str = item_part[item_part.find('(')+1:item_part.find(')')].strip()
                                quantidade = int(qty_str) if qty_str.isdigit() else 1
                            else:
                                nome = item_part.strip()
                                quantidade = 1
                            
                            # Buscar item no menu
                            for category, items in menu.items():
                                for menu_item in items:
                                    if menu_item['ativo'] and nome.lower() in menu_item['nome'].lower():
                                        order_data['items'].append({
                                            'id': menu_item['id'],
                                            'nome': menu_item['nome'],
                                            'quantidade': quantidade,
                                            'preco_unitario': menu_item['preco']
                                        })
                                        print(f"   ✓ Item adicionado: {menu_item['nome']} x{quantidade}")
                                        break
                    
                    elif line.startswith('CLIENTE:'):
                        order_data['cliente'] = line.replace('CLIENTE:', '').strip()
                    elif line.startswith('TELEFONE:'):
                        order_data['telefone'] = line.replace('TELEFONE:', '').strip()
                    elif line.startswith('ENTREGA:'):
                        order_data['tipo_entrega'] = line.replace('ENTREGA:', '').strip()
                    elif line.startswith('ENDERECO:'):
                        order_data['endereco'] = line.replace('ENDERECO:', '').strip()
                    elif line.startswith('PAGAMENTO:'):
                        order_data['forma_pagamento'] = line.replace('PAGAMENTO:', '').strip()
                
                # Se temos itens e informações básicas, criar pedido
                if order_data['items'] and order_data['cliente'] and order_data['telefone']:
                    # Calcular totais
                    subtotal = sum(item['preco_unitario'] * item['quantidade'] for item in order_data['items'])
                    taxa = restaurant['delivery']['taxa_entrega'] if 'delivery' in order_data['tipo_entrega'] else 0
                    
                    # Criar pedido completo
                    order = {
                        'id': generate_order_id(),
                        'timestamp': datetime.now().isoformat(),
                        'session_id': session_id,
                        'status': 'pendente',
                        'items': order_data['items'],
                        'cliente': order_data['cliente'],
                        'telefone': order_data['telefone'],
                        'tipo_entrega': order_data['tipo_entrega'],
                        'endereco': order_data['endereco'] if order_data['endereco'] != "retirada no local" else None,
                        'forma_pagamento': order_data['forma_pagamento'],
                        'subtotal': round(subtotal, 2),
                        'taxa_entrega': round(taxa, 2),
                        'total': round(subtotal + taxa, 2),
                        'observacoes': None
                    }
                    
                    # Salvar pedido
                    orders = load_json(ORDERS_FILE)
                    orders.append(order)
                    save_json(ORDERS_FILE, orders)
                    
                    order_created = True
                    order_id = order['id']
                    
                    print(f"✅ Pedido criado com sucesso: {order_id}")
                    print(f"📞 Telefone: {order['telefone']}")
                    print(f"💰 Total: R$ {order['total']}")
                    print(f"📦 Total de pedidos: {len(orders)}")
                    
                    # Limpar sessão
                    chat_sessions[session_id] = []
                    
            except Exception as e:
                print(f"❌ Erro ao processar pedido: {e}")
                import traceback
                traceback.print_exc()
        
        # Remover marcadores da resposta antes de enviar ao cliente
        bot_response_clean = bot_response
        if "###PEDIDO_CONFIRMADO###" in bot_response_clean:
            start = bot_response_clean.find("###PEDIDO_CONFIRMADO###")
            end = bot_response_clean.find("###FIM_PEDIDO###") + len("###FIM_PEDIDO###")
            bot_response_clean = bot_response_clean[:start] + bot_response_clean[end:]
            bot_response_clean = bot_response_clean.strip()
        
        return jsonify({
            'response': bot_response_clean,
            'order_created': order_created,
            'order_id': order_id
        })
        
    except Exception as e:
        print(f"❌ Erro no chat: {str(e)}")
        return jsonify({
            'response': 'Desculpe, ocorreu um erro. Por favor, tente novamente.',
            'error': str(e)
        }), 500

@app.route('/api/menu', methods=['GET'])
@login_required
def get_menu():
    """Retorna o cardápio completo"""
    return jsonify(load_json(MENU_FILE))

@app.route('/api/menu/item', methods=['POST'])
@login_required
def add_menu_item():
    """Adiciona um novo item ao cardápio"""
    data = request.json
    menu = load_json(MENU_FILE)
    
    # Gerar novo ID
    max_id = 0
    for items in menu.values():
        for item in items:
            max_id = max(max_id, item.get('id', 0))
    
    new_item = {
        'id': max_id + 1,
        'nome': data.get('nome', ''),
        'preco': float(data.get('preco', 0)),
        'descricao': data.get('descricao', ''),
        'categoria': data.get('categoria', ''),
        'ativo': data.get('ativo', True),
        'imagem': data.get('imagem', '')
    }
    
    category = data.get('categoria', '')
    if category in menu:
        menu[category].append(new_item)
        save_json(MENU_FILE, menu)
        return jsonify({'success': True, 'item': new_item})
    
    return jsonify({'success': False, 'message': 'Categoria inválida'}), 400

@app.route('/api/menu/item/<int:item_id>', methods=['PUT'])
@login_required
def update_menu_item(item_id):
    """Atualiza um item do cardápio"""
    data = request.json
    menu = load_json(MENU_FILE)
    
    for category_items in menu.values():
        for item in category_items:
            if item['id'] == item_id:
                item.update(data)
                save_json(MENU_FILE, menu)
                return jsonify({'success': True, 'item': item})
    
    return jsonify({'success': False, 'message': 'Item não encontrado'}), 404

@app.route('/api/menu/item/<int:item_id>', methods=['DELETE'])
@login_required
def delete_menu_item(item_id):
    """Remove um item do cardápio"""
    menu = load_json(MENU_FILE)
    
    for category, items in menu.items():
        menu[category] = [item for item in items if item['id'] != item_id]
    
    save_json(MENU_FILE, menu)
    return jsonify({'success': True})

@app.route('/api/restaurant', methods=['GET', 'PUT'])
@login_required
def restaurant_info():
    """Get ou atualiza informações do restaurante"""
    if request.method == 'GET':
        return jsonify(load_json(RESTAURANT_FILE))
    else:
        # Carregar dados atuais
        restaurant_data = load_json(RESTAURANT_FILE)
        
        # Atualizar com novos dados preservando estrutura
        update_data = request.json
        
        # Atualizar campos básicos
        if 'nome' in update_data:
            restaurant_data['nome'] = update_data['nome']
        if 'telefone' in update_data:
            restaurant_data['telefone'] = update_data['telefone']
        if 'endereco' in update_data:
            restaurant_data['endereco'] = update_data['endereco']
            
        # Atualizar horário de funcionamento
        if 'horario_funcionamento' in update_data:
            restaurant_data['horario_funcionamento'].update(update_data['horario_funcionamento'])
            
        # Atualizar configurações de delivery
        if 'delivery' in update_data:
            restaurant_data['delivery'].update(update_data['delivery'])
            
        # Atualizar formas de pagamento
        if 'pagamento' in update_data:
            restaurant_data['pagamento'].update(update_data['pagamento'])
            
        # Atualizar redes sociais
        if 'redes_sociais' in update_data:
            restaurant_data['redes_sociais'].update(update_data['redes_sociais'])
        
        # Salvar no arquivo JSON
        save_json(RESTAURANT_FILE, restaurant_data)
        
        return jsonify({'success': True, 'data': restaurant_data})

@app.route('/api/orders', methods=['GET'])
@login_required
def get_orders():
    """Retorna todos os pedidos"""
    return jsonify(load_json(ORDERS_FILE))

@app.route('/api/orders/<order_id>/status', methods=['PUT'])
@login_required
def update_order_status(order_id):
    """Atualiza o status de um pedido"""
    data = request.json
    new_status = data.get('status')
    
    orders = load_json(ORDERS_FILE)
    order_updated = False
    
    for order in orders:
        if order['id'] == order_id:
            order['status'] = new_status
            order['updated_at'] = datetime.now().isoformat()
            order_updated = True
            break
    
    if order_updated:
        # Salvar pedidos atualizados no JSON
        save_json(ORDERS_FILE, orders)
        print(f"✅ Status do pedido {order_id} atualizado para: {new_status}")
        
        # Retornar o pedido atualizado
        updated_order = next((o for o in orders if o['id'] == order_id), None)
        return jsonify(updated_order)
    
    return jsonify({'error': 'Pedido não encontrado'}), 404

@app.route('/api/analytics', methods=['GET'])
@login_required
def get_analytics():
    """Retorna análises dos pedidos"""
    orders = load_json(ORDERS_FILE)
    
    total_orders = len(orders)
    total_revenue = sum(order.get('total', 0) for order in orders)
    
    # Contar itens mais populares
    item_count = {}
    for order in orders:
        for item in order.get('items', []):
            name = item.get('nome', '')
            qty = item.get('quantidade', 0)
            item_count[name] = item_count.get(name, 0) + qty
    
    popular_items = sorted(item_count.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Contar pedidos por status
    status_count = {}
    for order in orders:
        status = order.get('status', 'pendente')
        status_count[status] = status_count.get(status, 0) + 1
    
    return jsonify({
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'average_order_value': total_revenue / total_orders if total_orders > 0 else 0,
        'popular_items': popular_items,
        'orders_by_status': status_count
    })

@app.route('/api/debug/files', methods=['GET'])
@login_required
def debug_files():
    """Endpoint de debug para verificar o estado dos arquivos JSON"""
    try:
        menu_data = load_json(MENU_FILE)
        restaurant_data = load_json(RESTAURANT_FILE)
        orders_data = load_json(ORDERS_FILE)
        
        return jsonify({
            'menu': {
                'exists': os.path.exists(MENU_FILE),
                'size': os.path.getsize(MENU_FILE) if os.path.exists(MENU_FILE) else 0,
                'items': sum(len(items) for items in menu_data.values()) if isinstance(menu_data, dict) else 0
            },
            'restaurant': {
                'exists': os.path.exists(RESTAURANT_FILE),
                'size': os.path.getsize(RESTAURANT_FILE) if os.path.exists(RESTAURANT_FILE) else 0,
                'name': restaurant_data.get('nome', 'N/A') if restaurant_data else 'N/A'
            },
            'orders': {
                'exists': os.path.exists(ORDERS_FILE),
                'size': os.path.getsize(ORDERS_FILE) if os.path.exists(ORDERS_FILE) else 0,
                'count': len(orders_data) if isinstance(orders_data, list) else 0
            },
            'files_path': os.getcwd()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Criar pasta templates se não existir
    os.makedirs('templates', exist_ok=True)
    
    # Inicializar arquivos JSON
    print("\n🚀 Inicializando GastroPlace...")
    initialize_files()
    
    # Verificar arquivos criados
    print("\n📁 Verificando arquivos JSON:")
    for filename in [MENU_FILE, RESTAURANT_FILE, ORDERS_FILE]:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"   ✅ {filename} ({size} bytes)")
        else:
            print(f"   ❌ {filename} não encontrado")
    
    print("\n🍽️  GastroPlace Chatbot iniciado!")
    print("📱 Chat disponível em: http://localhost:5000")
    print("🔐 Login disponível em: http://localhost:5000/login")
    print("📊 Dashboard disponível em: http://localhost:5000/dashboard (requer login)")
    print("🐛 Debug files: http://localhost:5000/api/debug/files")
    print("\n⚠️  Credenciais padrão: admin / admin123")
    print("⚠️  Lembre-se de configurar sua GEMINI_API_KEY!")
    
    app.run(debug=True, port=5004)