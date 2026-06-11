# Project Notes

## Visão geral

UltraTask é um app desktop em Python + Tkinter para gerenciamento local de tarefas.
O foco atual do projeto é produtividade pessoal com interface compacta, boa densidade de informação e iteração rápida sobre UX.

## Stack e execução

- Linguagem: Python
- UI: Tkinter
- Dependências principais: `tkcalendar`, `PyInstaller`
- Ambiente recomendado: `.venv` local
- Dependências declaradas em `requirements.txt`

## Arquivos importantes

- `app.py`: código principal do aplicativo
- `settings.json`: preferências locais do app
- `UltraTaskPortable.spec`: build portable via PyInstaller
- `dist/UltraTaskPortable/`: saída do executável portable

## Direção de produto

- A interface deve priorizar compactação visual.
- A lista principal deve mostrar o maior número possível de tarefas sem sacrificar legibilidade.
- Melhorias visuais são bem-vindas, mas não devem aumentar demais a altura útil das linhas da lista.
- O app já usa seções manuais para agrupamento de tarefas.
- Tags pertencem ao arquivo de tarefas atual, não são globais do aplicativo.

## Convenções de desenvolvimento

- Comentários no código devem ser em pt-BR.
- O padrão preferido é comentar por seções/blocos relevantes, explicando o papel do trecho sem poluir linha por linha.
- Ao fazer alterações de UX, preservar o estilo já consolidado do app em vez de reinventar a interface a cada ajuste.
- Quando uma ideia parecer arriscada, cara demais ou pouco útil, vale sinalizar isso antes de implementar.

## Convenções de commit

- Quando o usuário pedir commit, fazer push junto por padrão.
- Antes de commitar, limpar arquivos temporários gerados durante o trabalho, como previews e snapshots locais, salvo pedido em contrário.
- Evitar colocar em commit arquivos locais de uso pessoal ou artefatos transitórios.

## Arquivos locais que normalmente não entram em commit

- `BNDES.json`
- `build/`
- backups, previews e snapshots locais gerados durante a sessão
- outros arquivos de uso local do usuário que não façam parte do código do app

Observação:
`dist/UltraTaskPortable/` pode entrar em commit quando o objetivo for versionar a build portable.

## Estado atual das funcionalidades

- Tarefas com:
  - título
  - contato
  - designado
  - tags
  - data
  - importante
  - notas
- Seções manuais com cor personalizada
- Filtros por:
  - contato
  - designado
  - importância
  - tag
- Botão para limpar filtros
- Links automáticos em títulos de tarefas por regex
- Menu lateral compacto com ações principais
- Tela de tags com ordenação manual
- Tela de papéis com cores por arquivo
- Tela de links automáticos
- Notas com rich text
- Checklist dentro do campo de notas
- Build timestamp visível no app e compatível com versão portable
- Tags e papéis com largura fixa opcional por item
- Ordem configurável dos elementos da linha da tarefa por arquivo

## Notas sobre papéis

- O papel antigo de `responsável` foi renomeado para `contato`.
- Existe um segundo papel chamado `designado`.
- Os papéis são configurados em `Gerenciar papéis`.
- Cada papel possui:
  - cor
  - estilo (`tag` ou `balão`)
  - prefixo
  - fonte
  - tamanho opcional em caracteres para largura fixa
- A configuração dos papéis é salva no próprio arquivo de tarefas.
- Essa configuração não fica em `settings.json`.

## Notas sobre ordem da linha da tarefa

- A ordem visual da linha é salva no próprio arquivo de tarefas.
- Os tokens atualmente configuráveis são:
  - `tags`
  - `assignee`
  - `contact`
  - `title`
  - `date`
  - `notes`
  - `spacer`
- O marcador de importância continua fixo à esquerda.
- O botão de fechar continua fixo no fim da linha.
- Cada token pode aparecer no máximo uma vez e também pode ser omitido.

## Notas sobre tags

- As tags são salvas no `tag_catalog` do arquivo de tarefas atual.
- Cada tag possui nome, cor, ordem e tamanho opcional.
- Quando o tamanho estiver em branco, a largura da tag continua automática.
- Quando o tamanho estiver preenchido, a largura do chip passa a usar o valor fixo informado.

## Notas sobre links automáticos

- As regras ficam no `link_catalog` do arquivo de tarefas atual.
- Cada regra possui nome, regex e template de URL.
- O template aceita `{match}`, grupos numéricos como `{1}` e grupos nomeados como `{incidente}`.
- Os valores inseridos no template são codificados para uso em URL.
- Quando mais de uma regra casa o mesmo trecho, a primeira na ordem do catálogo prevalece.

## Notas sobre rich text

- As notas ricas são persistidas em HTML normalizado.
- O editor suporta:
  - negrito
  - itálico
  - sublinhado
  - tachado
  - cor da fonte
  - cor de fundo
  - checklist embutida no próprio texto
- A checklist convive com texto normal na mesma nota.

## Notas sobre performance

- Houve otimizações recentes para reduzir repaint completo da lista.
- O app já tenta reaproveitar linhas e evitar rerender global em alterações pequenas.
- Esse é um ponto sensível do projeto: mudanças nessa área devem ser testadas com atenção para evitar saltos de posição, piscadas e perda de scroll.

## Empacotamento

- O app gera uma versão portable com PyInstaller.
- No modo portable, o cálculo do build deve usar o executável, não depender de `app.py` dentro do bundle.

## Como retomar o projeto em outro computador

1. Clonar o repositório
2. Criar/ativar a `.venv`
3. Instalar `requirements.txt`
4. Ler este arquivo antes de continuar o desenvolvimento
5. Rodar `app.py`

## Próximos passos em aberto

- Continuar refinando a performance visual da lista principal
- Revisar a centralização vertical do título no header
- Continuar polindo ícones e pequenos detalhes de interface quando isso trouxer ganho real de UX
