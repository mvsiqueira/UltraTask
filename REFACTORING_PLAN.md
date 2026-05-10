# Plano de Refatoração do UltraTask

## Objetivo

O UltraTask começou como um app desktop simples em Python + Tkinter, mas já acumula funcionalidades suficientes para justificar uma separação interna melhor.

O objetivo desta refatoração não é trocar de tecnologia agora. A ideia é reduzir o tamanho e a responsabilidade do `app.py`, deixando o domínio do aplicativo menos acoplado à interface Tkinter. Isso melhora manutenção, testes, evolução de funcionalidades e também deixa uma migração futura para Qt, web local, Electron ou Tauri menos traumática caso um dia faça sentido.

## Direção Geral

Manter o app funcionando em Tkinter enquanto extraímos responsabilidades em módulos menores.

A refatoração deve ser incremental:

- evitar reescrita completa;
- preservar comportamento atual;
- mover uma responsabilidade por vez;
- testar o app após cada etapa;
- evitar mudanças visuais junto com mudanças estruturais grandes.

## Estrutura Sugerida

### `models.py`

Responsável pelos modelos de dados principais.

Conteúdo sugerido:

- `Task`
- tipos/constantes de item (`task`, `section`)
- helpers simples de normalização ligados ao modelo
- futuramente, tipos para catálogos de tags e links

Motivo:

Hoje `Task` está dentro de `app.py`, mas é domínio puro do aplicativo. Separá-lo reduz dependência da UI.

### `storage.py`

Responsável por leitura e gravação de arquivos.

Conteúdo sugerido:

- carregar arquivo de tarefas;
- salvar arquivo de tarefas;
- carregar/salvar `settings.json`;
- compatibilidade com formatos antigos;
- criação de arquivo inicial;
- validação básica do payload JSON.

Motivo:

Persistência hoje está misturada com fluxo de UI. Separar isso facilita testar e reduz risco ao mexer em telas.

### `tags.py`

Responsável pelo catálogo e regras de tags.

Conteúdo sugerido:

- limpar nome de tag;
- registrar tag;
- ordenar tags;
- reindexar catálogo;
- sincronizar tags usadas nas tarefas;
- obter cor;
- normalizar cores.

Motivo:

Tags já têm comportamento próprio: catálogo, cor, ordenação, seleção e filtros. Isso merece um módulo dedicado.

### `links.py`

Responsável pelos links automáticos por regex.

Conteúdo sugerido:

- carregar/normalizar regras de link;
- validar regex;
- validar template de URL;
- compilar regras;
- gerar URL a partir de match;
- quebrar título em segmentos normais e clicáveis.

Motivo:

Links automáticos são uma regra de domínio independente da UI. A renderização em Tkinter deve apenas consumir segmentos prontos.

### `notes.py`

Responsável por notas ricas e checklist.

Conteúdo sugerido:

- parsing de HTML simples;
- serialização de tags para HTML;
- normalização de checklist;
- regras de símbolos de checkbox;
- validação de payload `notes_rich`.

Motivo:

Notas são hoje uma das áreas mais complexas do app. Separar parser/serializer da tela de edição reduz bastante o peso mental do `app.py`.

### `ui_task_list.py`

Responsável pela lista principal de tarefas.

Conteúdo sugerido:

- renderização de tarefa;
- renderização de seção;
- indicadores visuais;
- drag-and-drop;
- seleção em lote;
- reaproveitamento de linhas;
- preservação de scroll.

Motivo:

A lista principal concentra boa parte da complexidade visual e de performance. Isolar isso ajuda a evoluir UI sem tocar em persistência, notas ou catálogos.

### `ui_dialogs.py`

Responsável por janelas auxiliares.

Conteúdo sugerido:

- diálogo de nova tarefa/seção;
- configurações;
- gerenciador de tags;
- gerenciador de links;
- diálogo de data;
- diálogo de seleção de tag;
- janela "Sobre".

Motivo:

Essas telas aumentam muito o tamanho de `app.py`, mas muitas são relativamente autocontidas.

### `app.py`

Depois da refatoração, deve ficar mais como orquestrador.

Responsabilidades finais desejadas:

- inicializar Tk;
- carregar settings/dados;
- montar shell principal;
- conectar módulos;
- coordenar refresh geral;
- manter estado de alto nível.

## Ordem Recomendada

### Fase 1: Baixo risco

1. Mover `Task` para `models.py`.
2. Mover `AppSettings` para `storage.py` ou `settings.py`.
3. Mover helpers de cor simples para um módulo utilitário se necessário.

Critério de sucesso:

- app abre;
- carrega arquivo atual;
- salva sem alterar formato inesperadamente.

### Fase 2: Catálogos

1. Extrair funções de tags para `tags.py`.
2. Extrair funções de links para `links.py`.
3. Manter as telas de tags/links ainda em `app.py` num primeiro momento.

Critério de sucesso:

- tags continuam com cor e ordem;
- filtros continuam funcionando;
- links clicáveis continuam funcionando;
- `link_catalog` e `tag_catalog` continuam no mesmo JSON.

### Fase 3: Persistência

1. Criar funções claras para carregar e salvar o payload completo.
2. Centralizar compatibilidade com formato antigo.
3. Reduzir acesso direto ao JSON dentro da UI.

Critério de sucesso:

- trocar arquivo em Configurações continua funcionando;
- arquivo inexistente ainda é criado corretamente;
- arquivos antigos continuam abrindo.

### Fase 4: Notas

1. Mover `NoteHTMLParser` para `notes.py`.
2. Mover serialização e validação de `notes_rich`.
3. Deixar em `app.py` apenas a montagem visual do editor, ou mover o editor depois.

Critério de sucesso:

- negrito, itálico, sublinhado e tachado persistem;
- cores persistem;
- checklist continua alternando e salvando;
- notas antigas continuam abrindo.

### Fase 5: Lista Principal

1. Extrair renderização de linhas para `ui_task_list.py`.
2. Isolar drag-and-drop.
3. Isolar seleção em lote.
4. Manter uma interface pequena entre lista e app principal.

Critério de sucesso:

- performance não piora;
- scroll não pula indevidamente;
- filtros e operações em lote funcionam;
- reordenação continua desativada com filtros ativos.

### Fase 6: Diálogos

1. Extrair gerenciador de tags.
2. Extrair gerenciador de links.
3. Extrair configurações.
4. Extrair sobre e prompts simples.

Critério de sucesso:

- `app.py` fica significativamente menor;
- telas continuam com o mesmo comportamento;
- callbacks ficam explícitos e fáceis de seguir.

## Cuidados

- Evitar refatorar UI e alterar comportamento visual no mesmo commit.
- Evitar mudar formato do JSON sem necessidade.
- Preservar compatibilidade com arquivos existentes.
- Testar operações com filtros ativos.
- Testar arquivos com seções, notas, links e tags.
- Não commitar arquivos locais de dados por acidente, especialmente `BNDES.json`, salvo quando for intencional.

## Sinais de Que Tkinter Pode Estar Chegando ao Limite

- necessidade frequente de hacks de layout;
- renderização da lista ficando difícil de manter;
- rich text exigindo mais recursos;
- necessidade de atalhos, menus, estados visuais e ícones mais sofisticados;
- dificuldade para testar componentes isolados.

Se esses sinais ficarem fortes, a refatoração modular ajuda a avaliar uma migração para PySide6/Qt ou para uma interface web local sem precisar reescrever toda a lógica de domínio.

## Recomendação Atual

Não migrar de tecnologia agora.

Primeiro, modularizar. Depois de reduzir o `app.py` e separar domínio, persistência e UI, reavaliar com mais clareza se Tkinter continua suficiente.
