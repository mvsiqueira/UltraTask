# UltraTask

App desktop para Windows, feito em Python + Tkinter, voltado para gerenciamento local de tarefas com foco em interface compacta e fluxo rápido de organização.

## Recursos

- Lista principal compacta, com alta densidade de informação
- Reordenação manual de tarefas por drag-and-drop
- Seções manuais para agrupamento visual
- Marcação de tarefa importante
- Responsável por tarefa
- Data de previsão por tarefa
- Tags com cor personalizada
- Gerenciador de tags com ordenação manual
- Links automáticos em títulos de tarefas por regex
- Filtros por:
  - responsável
  - importância
  - tag
- Botão para limpar filtros
- Notas por tarefa com rich text
- Checklist embutida no campo de notas
- Persistência local em arquivo JSON configurável
- Geração de executável portable para Windows

## Rich text nas notas

O editor de notas suporta:

- negrito
- itálico
- sublinhado
- tachado
- cor da fonte
- cor de fundo
- checklist misturada com texto normal

As notas ricas são persistidas em HTML normalizado.

## Links automáticos

O cadastro de links permite transformar trechos do título da tarefa em links clicáveis.

Cada regra define:

- nome
- expressão regular
- template de URL

O template de URL aceita marcadores como `{match}`, `{1}` e `{nome}` para inserir o texto capturado pela regex.

## Como executar em modo de desenvolvimento

1. Instale o Python 3.13 ou superior no Windows.
2. Abra um terminal na pasta do projeto.
3. Crie um ambiente virtual:

```powershell
python -m venv .venv
```

4. Ative o ambiente virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

5. Instale as dependências:

```powershell
pip install -r requirements.txt
```

6. Rode o app:

```powershell
python app.py
```

## Arquivos principais

- `app.py`: código principal do aplicativo
- `settings.json`: preferências locais
- `UltraTaskPortable.spec`: configuração da build portable
- `dist/UltraTaskPortable/`: saída do executável portable

## Configurações

Pela tela `Configurações`, é possível:

- escolher o arquivo JSON onde as tarefas serão armazenadas
- alternar o layout da lista
- escolher a cor usada no chip de responsável
- abrir o gerenciador de tags
- abrir o gerenciador de links automáticos

## Build portable

O projeto pode ser empacotado com PyInstaller para gerar uma versão portable do app.

Saída esperada:

- `dist/UltraTaskPortable/UltraTaskPortable.exe`

## Observações

- A ordem das tarefas é salva automaticamente.
- A reordenação da lista principal funciona apenas com os filtros limpos.
- O botão `Recarregar` relê o arquivo configurado no disco.
- Tags são específicas do arquivo de tarefas atual.
- Links automáticos são específicos do arquivo de tarefas atual.
- O arquivo de dados pode ficar em qualquer pasta acessível ao usuário, incluindo pastas sincronizadas pelo OneDrive.

## Documentação interna

- [PROJECT_NOTES.md](PROJECT_NOTES.md): memória operacional do projeto

Esse arquivo registra convenções de desenvolvimento, decisões de interface e contexto acumulado do app.
