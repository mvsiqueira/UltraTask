# UltraTask

App desktop para Windows, feito em Python + Tkinter, voltado para gerenciamento local de tarefas com foco em interface compacta e fluxo rápido de organização.

## Recursos

- Lista principal compacta, com alta densidade de informação
- Reordenação manual de tarefas por drag-and-drop
- Seções manuais para agrupamento visual
- Marcação de tarefa importante
- Contato por tarefa
- Designado por tarefa
- Data de previsão por tarefa
- Tags com cor personalizada
- Gerenciador de tags com ordenação manual
- Gerenciador de papéis com:
  - cor
  - estilo
  - prefixo
  - fonte
  - tamanho fixo opcional
- Ordem configurável dos elementos visuais na linha da tarefa
- Links automáticos em títulos de tarefas por regex
- Filtros por:
  - contato
  - designado
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
- abrir a configuração da ordem visual da linha da tarefa para o arquivo atual

As telas `Gerenciar tags`, `Gerenciar papéis` e `Gerenciar links` ficam disponíveis diretamente na barra lateral.

Os papéis `Contato` e `Designado` são configurados na tela `Gerenciar papéis` e ficam salvos no próprio arquivo de tarefas, incluindo cor, estilo, prefixo, fonte e tamanho fixo opcional.
A ordem visual da linha da tarefa também é salva no próprio arquivo de tarefas.

## Build portable

O projeto pode ser empacotado com PyInstaller para gerar uma versão portable do app.

Saída esperada:

- `dist/UltraTaskPortable/UltraTaskPortable.exe`

## Observações

- A ordem das tarefas é salva automaticamente.
- A reordenação da lista principal funciona apenas com os filtros limpos.
- O botão `Recarregar` relê o arquivo configurado no disco.
- Tags são específicas do arquivo de tarefas atual.
- Tags também podem ter largura fixa opcional, definida por item no cadastro.
- As cores de `Contato` e `Designado` também são específicas do arquivo atual.
- `Contato` e `Designado` também aceitam largura fixa opcional, definida por papel.
- A linha da tarefa aceita ordenar `Tags`, `Designado`, `Contato`, `Título`, `Data`, `Nota` e `Espaço` por arquivo.
- Links automáticos são específicos do arquivo de tarefas atual.
- O arquivo de dados pode ficar em qualquer pasta acessível ao usuário, incluindo pastas sincronizadas pelo OneDrive.

## Documentação interna

- [PROJECT_NOTES.md](PROJECT_NOTES.md): memória operacional do projeto

Esse arquivo registra convenções de desenvolvimento, decisões de interface e contexto acumulado do app.
