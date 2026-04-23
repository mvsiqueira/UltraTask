# UltraTask

App desktop para Windows feito em Python + Tkinter.

## Recursos

- Tarefas exibidas em linhas.
- Reordenacao manual por arrastar e soltar.
- Tags customizaveis por tarefa.
- Filtro por tag.
- Edicao, exclusao e marcacao de conclusao.
- Notas por tarefa com rich text basico: negrito, italico e sublinhado.
- Persistencia local em `tasks.json`.
- Pasta de armazenamento configuravel, inclusive dentro do OneDrive local.

## Como executar

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

5. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

6. Rode o app:

```powershell
python app.py
```

## Configuracoes

- Use o botao `Configuracoes` para abrir a janela de configuracoes.
- Nessa janela, voce escolhe a pasta onde o `tasks.json` sera salvo.
- Se selecionar uma pasta dentro do OneDrive instalado no Windows, a sincronizacao com a nuvem fica por conta do proprio OneDrive.

## Observacoes

- A ordem das tarefas e as tags ficam salvas automaticamente.
- A reordenacao funciona quando o filtro esta em `Todas`.
- O botao `Recarregar` relê o arquivo configurado no disco.
- O arquivo `settings.json` e o ambiente `.venv` nao entram no Git.
