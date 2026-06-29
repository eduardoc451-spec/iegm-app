"""
Script de Migração do Banco de Dados i-CIDADE
Adiciona colunas faltantes sem perder dados existentes
"""

import sqlite3
import os

def migrate_database(db_path="dados_iegm_web.db"):
    """Migra o banco de dados para a nova estrutura"""
    
    # Se o banco não existe, criar novo
    if not os.path.exists(db_path):
        print(f"✅ Criando novo banco de dados: {db_path}")
        create_new_database(db_path)
        return
    
    print(f"📊 Migrando banco de dados existente: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        # Verificar se a coluna atualizado_em já existe
        cursor.execute("PRAGMA table_info(respostas)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Adicionar colunas faltantes
        if "atualizado_em" not in columns:
            print("  ➕ Adicionando coluna 'atualizado_em'...")
            cursor.execute("""
                ALTER TABLE respostas 
                ADD COLUMN atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
        
        if "criado_em" not in columns:
            print("  ➕ Adicionando coluna 'criado_em'...")
            cursor.execute("""
                ALTER TABLE respostas 
                ADD COLUMN criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
        
        conn.commit()
        print("✅ Migração concluída com sucesso!")
        
        # Verificar dados
        cursor.execute("SELECT COUNT(*) FROM respostas")
        count = cursor.fetchone()[0]
        print(f"📈 Total de respostas no banco: {count}")
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        print(f"❌ Erro ao migrar: {e}")
        print("\n💡 Solução: Deletar o arquivo 'dados_iegm_web.db' e executar novamente.")
        raise

def create_new_database(db_path):
    """Cria um novo banco de dados com a estrutura correta"""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    
    # Tabela de respostas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS respostas (
            id TEXT NOT NULL,
            ano INTEGER NOT NULL,
            valor TEXT,
            pontos INTEGER DEFAULT 0,
            link TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, ano)
        )
    """)
    
    # Tabela de comentários
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comentarios (
            id TEXT NOT NULL,
            ano INTEGER NOT NULL,
            texto TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, ano)
        )
    """)
    
    # Tabela de auditorias
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditorias (
            ano INTEGER PRIMARY KEY,
            municipio TEXT,
            estado TEXT,
            responsavel TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Novo banco de dados criado com sucesso!")

if __name__ == "__main__":
    migrate_database()
