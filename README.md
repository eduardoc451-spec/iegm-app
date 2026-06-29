# IEG-M Francisco Morato - Sistema Streamlit

Sistema de gestão e análise de indicadores IEG-M (Indicadores de Efetividade da Gestão Municipal) para o município de Francisco Morato.

## 🚀 Funcionalidades

- **Autenticação Segura**: Login com usuário e senha
- **Menu de Dimensões**: Seleção entre 7 dimensões (i-Cidade, i-Gov TI, i-Amb, i-Plan, i-Fiscal, i-Educ, i-Saúde)
- **Módulo i-Cidade**: Formulário com 34 quesitos e pontuação automática (usando código original preservado)
- **Gráficos Interativos**: Série histórica e faixa de desempenho
- **Relatório PDF**: Análise de pontos fortes e críticos com classificação de relevância
- **Banco de Dados SQLite**: Persistência de respostas e histórico

## 📁 Estrutura de Arquivos

```
ieg-m-streamlit/
├── app.py                    # Aplicação principal Streamlit
├── icidade_original.py       # Módulo i-Cidade original preservado (2398 linhas)
├── constants.py              # Constantes (quesitos, pontuação)
├── database.py               # Gerenciamento de banco de dados SQLite
├── scoring.py                # Funções de cálculo de pontuação
├── pdf_generator.py          # Geração de relatório PDF
├── requirements.txt          # Dependências do projeto
├── README.md                 # Este arquivo
└── ieg_m_database.db         # Banco de dados SQLite (criado automaticamente)
```

## 📋 Arquivos Principais

### `icidade_original.py` (Preservado)
- Arquivo original completo com 2398 linhas
- Contém toda a lógica do módulo i-Cidade
- Integrado automaticamente ao iniciar a aplicação
- Funções principais:
  - `main()` - Função principal que renderiza o módulo
  - `init_db()` - Inicializa banco de dados
  - `load_respostas()` - Carrega respostas por ano
  - `save_resp()` - Salva resposta de quesito
  - `analyze_performance()` - Analisa desempenho
  - `analyze_recurrence()` - Analisa reincidências
  - `gerar_relatorio_pdf()` - Gera relatório PDF

### `app.py`
- Aplicação principal com login e dashboard
- Integra o módulo icidade_original.py
- Gerencia navegação entre dimensões

### `constants.py`
- Constantes globais (quesitos, pontuação, dimensões)
- Categorias de quesitos
- Faixas de desempenho

### `database.py`
- Gerenciamento de usuários
- Persistência de respostas
- Histórico de pontuação

## 📋 Requisitos

- Python 3.8+
- pip (gerenciador de pacotes Python)

## 🔧 Instalação

1. **Clonar ou baixar o projeto**:
```bash
cd ieg-m-streamlit
```

2. **Criar ambiente virtual (opcional, mas recomendado)**:
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Instalar dependências**:
```bash
pip install -r requirements.txt
```

## 🎯 Como Usar

### Iniciar a aplicação:
```bash
streamlit run app.py
```

A aplicação abrirá automaticamente no navegador em `http://localhost:8501`

### Credenciais de Acesso:
- **Usuário**: jefferson.espanha
- **Senha**: fodase

### Fluxo de Uso:

1. **Login**: Acesse com as credenciais padrão
2. **Dashboard**: Selecione o ano de referência e a dimensão desejada
3. **Módulo i-Cidade**: 
   - Preencha os 34 quesitos com respostas e pontuação
   - Clique em "Salvar" para cada quesito
4. **Gráficos**: Visualize a série histórica e faixa de desempenho
5. **Relatório**: Gere análise com pontos fortes e críticos
6. **PDF**: Baixe o relatório em PDF

## 📊 Quesitos do i-Cidade

O módulo i-Cidade contém 34 quesitos com pontuação máxima e mínima definida:

- **1.0**: 0-40 pontos
- **1.3**: 0-5 pontos
- **1.4**: 0-50 pontos
- **2.0**: 0-20 pontos
- **2.1**: 0-30 pontos
- **2.2**: 0-10 pontos
- **3.0**: 0-10 pontos
- **3.1**: 0-10 pontos
- **4.2**: 0-10 pontos
- **5.0**: 0-30 pontos
- **5.1.1**: 0-20 pontos
- **5.2**: 0-10 pontos
- **6.0**: 0-30 pontos
- **7.0**: 0-30 pontos
- **7.1**: 0-10 pontos
- **7.2**: 0-80 pontos
- **7.3**: 0-10 pontos
- **7.4**: 0-10 pontos
- **7.5**: 0-10 pontos
- **7.6**: 0-10 pontos
- **8.0**: 0-30 pontos
- **8.1.1.1**: 0-20 pontos
- **8.2**: 0-10 pontos
- **9.0**: 0-30 pontos
- **10.0**: -100 a 0 pontos
- **11.1**: 0-20 pontos
- **11.1.1**: 0-10 pontos
- **11.2**: 0-10 pontos
- **12.1**: 0-20 pontos
- **12.1.3**: 0-10 pontos
- **14.0**: 0-30 pontos
- **15.0**: 0-30 pontos
- **16.0**: 0-30 pontos
- **C1.1**: -30 a 0 pontos

## 📈 Faixas de Desempenho

| Faixa | Pontuação | Cor |
|-------|-----------|-----|
| C | 0-500 | Vermelho |
| C+ | 500-600 | Laranja |
| B | 600-750 | Amarelo |
| B+ | 750-900 | Verde Claro |
| A | 900+ | Verde |

## 🎨 Classificação de Relevância

Pontos críticos são classificados por relevância de perda de pontuação:

- **Baixa**: 1-5 pontos perdidos
- **Média**: 6-15 pontos perdidos
- **Alta**: 16+ pontos perdidos

## 📄 Relatório PDF

O relatório PDF inclui:

1. **Informações Gerais**: Dimensão, ano, pontuação total, faixa
2. **Pontos Fortes**: Quesitos na pontuação máxima
3. **Pontos Críticos**: Classificados por relevância (Alta, Média, Baixa)
4. **Reincidências**: Quesitos com pontuação zero/negativa em anos anteriores
5. **Histórico Geral**: Todas as respostas com evidências

## 🔐 Segurança

- Senhas são armazenadas em texto plano no SQLite (para desenvolvimento)
- Para produção, implemente hash de senhas (bcrypt, argon2, etc)
- Considere adicionar autenticação OAuth/LDAP

## 🛠️ Personalização

### Adicionar novo usuário:

Edite `database.py` e adicione na função `init_database()`:
```python
add_user("novo_usuario", "senha", "user")
```

### Modificar quesitos:

Edite `constants.py` e atualize o dicionário `CATEGORIAS_MAP` e `PONTUACOES_MAX`

### Alterar faixas de desempenho:

Edite `constants.py` e atualize `FAIXA_CORES`

## 📞 Suporte

Para dúvidas ou problemas, verifique:
- Logs do Streamlit (console)
- Arquivo de banco de dados: `ieg_m_database.db`
- Arquivo de requisitos: `requirements.txt`

## 📝 Licença

© 2026 IEG-M Francisco Morato - Todos os direitos reservados

## 🚀 Próximas Versões

- [ ] Implementar outras dimensões (i-Gov TI, i-Amb, i-Plan, i-Fiscal, i-Educ, i-Saúde)
- [ ] Gerenciamento de usuários (admin)
- [ ] Histórico de alterações
- [ ] Exportação em outros formatos (Excel, CSV)
- [ ] Gráficos comparativos entre anos
- [ ] Análise de tendências

---

**Versão 1.0** | Desenvolvido em Python com Streamlit | 2026 | Arquivo icidade_original.py preservado e integrado
