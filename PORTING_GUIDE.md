# UltraTask - Especificação Funcional e Guia de Portabilidade

## Objetivo deste documento

Este documento descreve o comportamento funcional do UltraTask de forma suficiente para permitir a reimplementação do aplicativo em outra linguagem, framework ou plataforma sem depender:

- do código-fonte atual
- do histórico de conversas
- de conhecimento implícito do projeto

Ele deve ser tratado como a referência principal para portar o app para outro stack.

## Visão geral do produto

UltraTask é um gerenciador local de tarefas com foco em:

- alta densidade de informação por linha
- velocidade de organização manual
- persistência simples em JSON
- customização visual por arquivo de tarefas

O aplicativo não depende de backend. Toda a persistência relevante é feita em arquivos locais.

## Princípios de UX

- A lista principal deve exibir o maior número possível de tarefas na tela.
- Alterações visuais não devem aumentar desnecessariamente a altura das linhas.
- A interface deve privilegiar operações diretas com mouse, com poucos cliques.
- Itens visuais como tags, papéis e data devem ser legíveis, mas compactos.
- O app permite customização, mas sem virar um editor genérico de layout.

## Conceitos de domínio

### Tarefa

Item padrão da lista. Pode conter:

- título
- contato
- designado
- tags
- data
- notas
- marcação de importante

### Seção

Linha especial usada para agrupar visualmente tarefas. Seções não se comportam como tarefas comuns.

### Contato

Papel configurável por arquivo, herdado do antigo conceito de "responsável".

### Designado

Segundo papel configurável por arquivo, independente de Contato.

### Tag

Rótulo colorido associado à tarefa. As tags pertencem ao arquivo de tarefas atual.

### Regra de link

Regra baseada em regex que transforma trechos do título em links clicáveis.

## Arquivos persistidos

### 1. `settings.json`

Arquivo global do aplicativo. Armazena apenas preferências locais do app, não os dados da lista.

Campos esperados:

- caminho do arquivo de tarefas atual
- modo de layout da lista

Observação:

- configurações específicas da lista não devem ficar aqui
- ao trocar de arquivo de tarefas, o app passa a usar os metadados daquele arquivo

### 2. Arquivo de tarefas JSON

É o arquivo principal de dados do usuário. Ele concentra:

- título do arquivo
- tarefas e seções
- catálogo de tags
- configuração de papéis
- catálogo de links
- ordem visual da linha da tarefa

Estrutura de alto nível:

```json
{
  "title": "UltraTask - Exemplo",
  "tasks": [],
  "task_row_order": ["tags", "assignee", "contact", "title", "notes", "spacer", "date"],
  "role_config": {
    "contact": {},
    "assignee": {}
  },
  "tag_catalog": [],
  "link_catalog": []
}
```

## Modelo de dados do arquivo de tarefas

### Campo `title`

Título lógico do arquivo/lista. É exibido no cabeçalho principal.

### Campo `tasks`

Lista de objetos. Cada objeto pode representar:

- uma tarefa comum
- uma seção

### Estrutura de item da lista

Campos persistidos:

```json
{
  "id": "uuid",
  "title": "Texto do item",
  "completed": false,
  "important": false,
  "due_date": "",
  "notes": "",
  "notes_rich": null,
  "contact": "",
  "assignee": "",
  "tags": [],
  "item_type": "task",
  "section_color": "#B45309"
}
```

Semântica:

- `id`: identificador único estável
- `title`: texto principal
- `completed`: tarefa concluída; afeta estilo visual do título
- `important`: ativa a “orelha” vermelha à esquerda
- `due_date`: data em formato persistido pelo app
- `notes`: texto simples legado
- `notes_rich`: payload rico normalizado
- `contact`: valor textual do papel Contato
- `assignee`: valor textual do papel Designado
- `tags`: lista de nomes de tags
- `item_type`: `"task"` ou `"section"`
- `section_color`: cor da seção

### Regras para item do tipo `section`

Quando `item_type = "section"`:

- `tags` deve ficar vazio
- `completed` deve ser `false`
- `important` deve ser `false`
- `due_date` deve ser vazio
- `notes` deve ser vazio
- `notes_rich` deve ser `null`
- `contact` deve ser vazio
- `assignee` deve ser vazio

Em outras palavras: seção só usa título, tipo e cor.

## Catálogo de tags

Estrutura:

```json
[
  {
    "name": "ALÇADAS",
    "color": "#2563EB",
    "order": 0,
    "size": ""
  }
]
```

Semântica:

- `name`: nome exibido
- `color`: cor do chip
- `order`: ordem de exibição da tag no app
- `size`: largura fixa opcional em caracteres; vazio significa largura automática

Regras:

- tags são específicas do arquivo atual
- nomes são tratados de forma case-insensitive para identidade
- a exibição preserva o nome normalizado salvo no catálogo
- tags descobertas apenas dentro de tarefas devem ser promovidas para o catálogo

## Configuração de papéis

Estrutura:

```json
{
  "contact": {
    "color": "#0F766E",
    "style": "balloon",
    "prefix": "@",
    "font": "Segoe UI",
    "size": ""
  },
  "assignee": {
    "color": "#7C3AED",
    "style": "balloon",
    "prefix": "→",
    "font": "Segoe UI",
    "size": ""
  }
}
```

Semântica:

- `color`: cor do chip
- `style`: `"tag"` ou `"balloon"`
- `prefix`: prefixo textual; vazio é permitido e deve resultar em chip sem prefixo
- `font`: fonte usada no texto do chip
- `size`: largura fixa opcional em caracteres; vazio significa largura automática

Observações importantes:

- Contato e Designado são configuráveis por arquivo
- o prefixo vazio deve ser respeitado
- o fallback para prefixo default só deve acontecer quando a configuração não existir no arquivo

## Catálogo de links

Estrutura:

```json
[
  {
    "id": "uuid",
    "name": "Incidente",
    "pattern": "INC(?P<num>\\d+)",
    "url_template": "https://exemplo/{match}",
    "order": 0
  }
]
```

Semântica:

- `id`: identificador estável da regra
- `name`: nome descritivo
- `pattern`: regex
- `url_template`: template com placeholders
- `order`: precedência visual e lógica

Regras do template:

- aceita `{match}` para o trecho completo
- aceita grupos numéricos, por exemplo `{1}`
- aceita grupos nomeados, por exemplo `{num}`
- os valores inseridos devem ser codificados para URL
- quando múltiplas regras casarem o mesmo trecho, a primeira na ordem prevalece

## Ordem visual da linha da tarefa

Campo:

```json
["tags", "assignee", "contact", "title", "notes", "spacer", "date"]
```

Tokens válidos configuráveis:

- `tags`
- `assignee`
- `contact`
- `title`
- `date`
- `notes`
- `spacer`

Regras:

- cada token pode aparecer 0 ou 1 vez
- a ordem da lista define a ordem de renderização
- lista vazia é válida
- `important` não faz parte desse array
- o botão de exclusão não faz parte desse array

Itens fixos fora da configuração:

- marcador de importância sempre à esquerda
- botão de excluir sempre no final da linha

Semântica especial de `spacer`:

- representa um espaço expansível
- sua função é empurrar elementos posteriores para a direita

## Interface principal

## Cabeçalho

Elementos:

- título do arquivo
- botão Sobre
- botão Configurações
- timestamp de build

## Barra lateral

Contém ações principais do app, em formato compacto com ícones e tooltip.

Ações atuais:

- adicionar tarefa
- adicionar seção
- operações em lote
- recarregar
- gerenciar tags
- gerenciar papéis
- gerenciar links
- configurações
- sobre

## Linha de filtros

Filtros atuais:

- Tag
- Responsável/Contato
- Designado
- Importância
- botão Limpar filtros

Observação:

- os filtros refletem apenas valores presentes no arquivo atual

## Lista principal

A lista principal exibe tarefas e seções.

### Estrutura fixa da linha de tarefa

Da esquerda para a direita:

1. orelha de importância
2. grip de drag-and-drop
3. checkbox de lote, quando o modo de lote está ativo
4. área de conteúdo configurável
5. botão de excluir

### Tokens renderizáveis dentro da área de conteúdo

#### `tags`

- renderiza os chips das tags
- a ordem das tags deve obedecer o `tag_catalog`
- clique esquerdo abre edição de tags da tarefa
- clique direito abre menu contextual da tag

#### `assignee`

- renderiza o chip de Designado, se houver valor
- clique esquerdo altera o designado da tarefa
- clique direito filtra por esse designado

#### `contact`

- renderiza o chip de Contato, se houver valor
- clique esquerdo altera o contato da tarefa
- clique direito filtra por esse contato

#### `title`

- renderiza o título da tarefa
- suporta edição inline
- suporta links automáticos
- quando a tarefa está concluída, o título fica tachado

#### `notes`

- renderiza um badge/ícone pequeno indicando existência de nota
- clique esquerdo abre o editor de notas
- o badge deve ocupar um slot próprio e não ficar colado aos itens vizinhos

#### `spacer`

- expande para ocupar o espaço restante

#### `date`

- renderiza a data da tarefa
- clique esquerdo abre o seletor de data
- a largura visual deve ser justa ao conteúdo, sem reserva exagerada

## Seções

### Aparência

- linha separadora horizontal
- título destacado
- cor configurável por seção

### Comportamento

- pode ser reposicionada na lista
- serve como agrupamento visual
- não herda campos de tarefa comum

## Edição inline do título

### Tarefa comum

- clicar no texto ativa edição inline
- `Enter` confirma
- `Escape` cancela
- perda de foco confirma

### Título do arquivo

- também pode ser editado inline no cabeçalho

## Reordenação manual

### Lista principal

- usa drag-and-drop
- a ordem manual é persistida
- deve preservar a posição visual ao máximo durante repaints

Restrição:

- a reordenação só é confiável com filtros limpos

### Cadastro de tags

- usa botões de mover para cima/baixo
- a ordem das tags impacta a exibição dos chips nas tarefas

## Operações em lote

Quando o modo de lote está ativo:

- tarefas exibem checkbox de seleção
- seções podem selecionar em lote as tarefas do grupo

Ações atuais:

- adicionar tag
- remover tag
- definir designado
- definir contato
- marcar importante
- desmarcar importante
- excluir
- limpar seleção

## Menus de contexto

### Menu da tarefa

Ordem atual:

1. Editar
2. separador
3. Marcar como importante
4. Alterar tags
5. Definir responsável/contato
6. Definir designado
7. Definir data
8. Adicionar notas
9. separador
10. Duplicar
11. Excluir

Observação:

- a nomenclatura visual atual deve refletir `Contato` e `Designado`

### Menu contextual de tag

- Filtrar por tag `<nome>`

### Menu contextual de contato

- Filtrar por contato `<nome>`

### Menu contextual de designado

- Filtrar por designado `<nome>`

## Tela Gerenciar tags

Funções:

- criar tag
- escolher cor
- definir tamanho fixo opcional
- renomear
- excluir
- alterar ordem manual

Regras:

- a lista deve ter scroll funcional com mouse
- a barra de scroll deve aparecer quando necessário
- a tela principal só precisa ser atualizada ao fechar a janela em cenários de ordenação

## Tela Gerenciar papéis

Papéis configuráveis:

- Designado
- Contato

Campos por papel:

- prévia
- cor
- estilo
- prefixo
- tamanho
- fonte

Regras:

- a prévia deve reagir imediatamente às alterações
- `prefixo` pode ficar vazio
- `tamanho` vazio significa largura automática
- o layout deve manter labels e campos alinhados

## Tela Gerenciar links

Funções:

- criar regra
- editar regra
- excluir regra
- reordenar regras

Cada regra possui:

- nome
- regex
- template de URL

## Tela de notas

## Objetivo

Permitir texto livre com formatação leve e checklist dentro da mesma nota.

## Toolbar

Comandos suportados:

- negrito
- itálico
- sublinhado
- tachado
- cor da fonte
- cor de fundo
- inserir checklist

Observações de UX:

- labels da toolbar usam iniciais compactas em pt-BR
- atalhos ficam em tooltip, não impressos no layout

## Persistência das notas

As notas ricas são persistidas em HTML normalizado.

A implementação de outra plataforma deve preservar a semântica, não necessariamente a serialização idêntica caractere a caractere, desde que:

- o HTML resultante seja válido
- estilos equivalentes sejam preservados
- checklist continue convivendo com texto normal

## Checklist embutida

Símbolos:

- desmarcada: `☐`
- marcada: `☒`

Regras:

- checklist pode coexistir com texto comum na mesma nota
- clicar na área da checkbox alterna o estado
- o cursor deve indicar interatividade sobre a checkbox
- a troca de estado deve preservar o restante do conteúdo da linha

## Filtros

Filtros suportados:

- por tag
- por contato
- por designado
- por importância

Regras:

- filtro de contato/designado deve ser case-insensitive
- botão “Limpar filtros” deve zerar todos os filtros

## Regras de renderização e desempenho

- a lista não deve saltar para o topo a cada edição simples
- alterações pequenas devem tentar reaproveitar widgets/linhas existentes
- mudanças em tags, papéis, texto inline e filtros devem preservar o scroll quando possível
- a performance visual é um requisito importante do produto

## Build e empacotamento

### Modo desenvolvimento

Stack atual:

- Python
- Tkinter
- `tkcalendar`

### Modo portable

O app gera executável portable.

Requisito funcional importante:

- o timestamp de build deve continuar funcionando mesmo em modo empacotado
- no modo portable, o cálculo deve usar o executável quando `app.py` não estiver disponível

## Diretrizes para portar para outra plataforma

Uma nova implementação deve preservar obrigatoriamente:

- modelo de dados do arquivo JSON
- semântica de tarefa versus seção
- configuração por arquivo de tags, papéis, links e ordem da linha
- edição inline de título
- drag-and-drop da lista principal
- operações em lote
- notas ricas com checklist
- filtros e menus contextuais
- alta densidade visual

Pode variar entre plataformas:

- biblioteca gráfica
- toolkit
- mecanismo de rich text
- aparência exata dos ícones
- estratégia interna de reaproveitamento de widgets

## Sugestão de módulos para reimplementação

Uma nova implementação pode ser dividida em:

1. persistência
2. modelo de domínio
3. regras de ordenação e filtros
4. renderização da lista principal
5. editores auxiliares:
   - tags
   - papéis
   - links
   - notas
   - configurações
6. empacotamento

## Casos de compatibilidade importantes

- abrir arquivo antigo sem `task_row_order`
- abrir arquivo antigo sem `role_config` estruturado
- abrir tarefas antigas com `notes` simples
- abrir arquivo com tags presentes apenas dentro das tarefas
- respeitar prefixo vazio de papéis
- permitir lista vazia em `task_row_order`

## Critérios mínimos de aceite para uma porta

Uma porta para outra plataforma deve ser considerada funcionalmente equivalente se:

1. conseguir abrir e salvar o mesmo arquivo JSON sem perda de semântica
2. preservar a organização manual da lista
3. renderizar corretamente tarefas, seções, tags, contato, designado, data e nota
4. suportar configuração visual de tags e papéis por arquivo
5. suportar a ordenação configurável dos elementos da linha
6. manter notas ricas com checklist
7. oferecer filtros, contexto e operações em lote equivalentes
8. manter a proposta de alta densidade visual

## Exemplo completo de arquivo de tarefas

O exemplo abaixo mostra um arquivo plausível contendo:

- título da lista
- tarefas comuns
- uma seção
- ordem configurável da linha
- configuração completa de papéis
- catálogo de tags
- catálogo de links
- nota rica persistida em HTML

```json
{
  "title": "UltraTask - BNDES",
  "tasks": [
    {
      "id": "8e0f0f8f-9d39-4d9f-9b7c-12c3f9b8d001",
      "title": "ALÇADAS",
      "completed": false,
      "important": false,
      "due_date": "",
      "notes": "",
      "notes_rich": null,
      "contact": "",
      "assignee": "",
      "tags": [],
      "item_type": "section",
      "section_color": "#B45309"
    },
    {
      "id": "8e0f0f8f-9d39-4d9f-9b7c-12c3f9b8d002",
      "title": "Ajustar perfis da ACO",
      "completed": false,
      "important": false,
      "due_date": "",
      "notes": "",
      "notes_rich": {
        "html": "<p>Validar perfis com a equipe.</p><p><span style=\"color:#1d4ed8;\">☐</span> Revisar lista atual</p><p><span style=\"color:#1d4ed8;\">☒</span> Confirmar usuários críticos</p>"
      },
      "contact": "ATOS",
      "assignee": "",
      "tags": ["ALÇADAS", "Funções 2"],
      "item_type": "task",
      "section_color": "#B45309"
    },
    {
      "id": "8e0f0f8f-9d39-4d9f-9b7c-12c3f9b8d003",
      "title": "Pendências GDIV",
      "completed": false,
      "important": false,
      "due_date": "2026-05-01",
      "notes": "",
      "notes_rich": null,
      "contact": "",
      "assignee": "",
      "tags": ["ALÇADAS", "MONPAG", "GDIV"],
      "item_type": "task",
      "section_color": "#B45309"
    },
    {
      "id": "8e0f0f8f-9d39-4d9f-9b7c-12c3f9b8d004",
      "title": "INC000004425804 - Dados aprovação fatura - Homologar",
      "completed": false,
      "important": true,
      "due_date": "",
      "notes": "",
      "notes_rich": {
        "html": "<p><strong>Checar</strong> a aprovação com o financeiro.</p>"
      },
      "contact": "Fernanda",
      "assignee": "",
      "tags": ["ALÇADAS", "MONPAG", "GDIV"],
      "item_type": "task",
      "section_color": "#B45309"
    }
  ],
  "task_row_order": [
    "assignee",
    "contact",
    "notes",
    "tags",
    "date",
    "title"
  ],
  "role_config": {
    "contact": {
      "color": "#FFF200",
      "style": "balloon",
      "prefix": "@",
      "font": "Verdana",
      "size": ""
    },
    "assignee": {
      "color": "#BDBDBD",
      "style": "tag",
      "prefix": "",
      "font": "Courier New",
      "size": "7"
    }
  },
  "tag_catalog": [
    {
      "name": "ALÇADAS",
      "color": "#0F8B8D",
      "order": 0,
      "size": ""
    },
    {
      "name": "Funções 2",
      "color": "#F5D0FE",
      "order": 1,
      "size": "12"
    },
    {
      "name": "MONPAG",
      "color": "#BE185D",
      "order": 2,
      "size": ""
    },
    {
      "name": "GDIV",
      "color": "#F40076",
      "order": 3,
      "size": ""
    }
  ],
  "link_catalog": [
    {
      "id": "8e0f0f8f-9d39-4d9f-9b7c-12c3f9b8d101",
      "name": "Incidente",
      "pattern": "INC(?P<num>\\d+)",
      "url_template": "https://exemplo.local/incidentes/{match}",
      "order": 0
    }
  ]
}
```

## Observações sobre o exemplo

- A primeira entrada é uma seção, por isso os campos de tarefa comum estão vazios.
- A tarefa com `important = true` deve exibir a orelha vermelha fixa à esquerda.
- `contact` usa estilo `balloon` com prefixo `@`.
- `assignee` usa estilo `tag`, sem prefixo, com largura fixa `7`.
- `task_row_order` não inclui `spacer`, então o título deve ocupar o espaço disponível restante.
- O conteúdo de `notes_rich` ilustra a persistência em HTML normalizado; outra implementação pode gerar HTML equivalente, sem precisar reproduzir exatamente cada caractere do exemplo.
