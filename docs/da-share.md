# D&A Share — contribuição por Claude Code

## Por que existe

O vault central nao deve exigir que cada pessoa aprenda Obsidian, pastas, nomes de arquivo e
frontmatter antes de conseguir compartilhar uma decisao ou aprendizado. Claude Code e a
interface que o time ja usa; o vault continua sendo o registro institucional.

O que veio antes foi um fluxo de graduacao manual, e ele nao pegou. Em dois meses de vault
central com 182 notas, exatamente 2 vieram do vault pessoal de outra pessoa (Pedro Hennig e
Daniel Lima, ambas em 2026-08-05, ambas graduadas pelo Kelvin). O resto e Kelvin ou automacao.
Isso e o numero que este pacote tenta mudar, e e por ele que o piloto deve ser medido.

## Experiência do colaborador

No terminal, a pessoa abre Claude Code e escreve algo como:

> Compartilhe esta decisao com o D&A: a partir de outubro, o acesso PBI da BU X sera tratado pelo grupo Y.

`/da-compartilhar` cria uma previa, verifica o conteudo e pede uma confirmacao explicita.
Com o "sim", cria uma submissao imutavel em `Intake/YYYY-MM/`. A pessoa nao abre Obsidian e
nao escolhe uma pasta de destino.

Depois, `queue --author` responde "o que aconteceu com o que eu mandei".

## Experiência do dono

O dono abre Claude Code e pede: `revisar minhas pendencias do D&A`. `/da-revisar` mostra a
fila inteira de uma vez, com recomendacao por item, e espera instrucao.

- **Publicar** cria uma nota nova no projeto/area e um recibo em `Intake/Receipts/`.
- **Devolver** ou **rejeitar** grava a decisao e o motivo em `Intake/_decisions/`.

Os dois caminhos gravam um arquivo de decisao, e e ele que tira o item da fila. Sem isso a
fila so cresce: a primeira versao tinha apenas `publish`, entao uma submissao devolvida ficava
`pending-review` para sempre e reaparecia em toda revisao.

Nada e movido, editado ou apagado, nunca.

Cada recibo usa tambem o identificador da submissao, alem do horario. Assim, duas notas com
o mesmo nome (por exemplo, `Status.md` em projetos distintos) publicadas no mesmo segundo
continuam com recibos independentes e auditaveis.
A submissao tambem inclui um digest no nome imutavel. Isso evita colisao quando titulos longos
compartilham o mesmo prefixo e chegam no mesmo segundo.

## A fronteira de escrita

`scripts/da_intake.py` e a unica coisa que grava. Ele recusa em tres situacoes.

| Situacao | O que acontece |
|---|---|
| Dinheiro de pessoa, saude, identidade, credencial | Recusa, sem flag de contorno |
| Palavra ambigua (`promotion`, `headcount`, `politica`) | Pergunta uma vez; `confirm_not_personal` grava a resposta |
| Destino que nao existe | Recusa e sugere os parecidos; `allow_new_folder` libera |

Os padroes sao os mesmos do `vault-central-sensitive-scan.ps1`, que roda 18:25 todo dia. A
diferenca e o momento: o scan **relata** o que ja esta no SharePoint ha horas, e este programa
**recusa** antes de gravar. As duas listas precisam andar juntas; quando uma mudar, mude a outra.

Duas ampliacoes entraram em 2026-09-11, achadas testando e nao lendo:

- `sal[aá]ri` no lugar de `sal(a|á)rio`, porque "banda salarial" nao casava e uma submissao
  sobre faixa salarial passou limpa no teste.
- Grupo `personal` (PLR, atestado, CPF, cidadania, processo judicial), que sao os assuntos que
  se acumularam na triagem do Inbox de 2026-09-10.

Medido contra as 182 notas existentes, a ampliacao nao produziu nenhum achado novo.

## Por que dois niveis e nao um

Um nivel unico seria contornado na primeira semana. `promotion` e etapa de pipeline e
`headcount` e coluna do spec do QBR, e os dois ja estao escritos no vault sobre maquina, nao
sobre gente. Um portao que recusa esses sem saida vira um portao que a pessoa aprende a driblar,
e ai ele nao protege mais nada. Entao: recusa dura no que nunca tem motivo para estar la,
pergunta unica e registrada no que e ambiguo.

## Governança

- O autor confirma o envio; o modelo nao compartilha sozinho.
- O dono do projeto/area aprova a publicacao no seu escopo. Kelvin decide excecoes,
  conteudo sensivel, areas sem dono e mudancas de estrutura.
- A skill nao le, guarda ou transmite API keys. A chave continua so no Claude Code da pessoa.
- `DA_CENTRAL_VAULT` aponta para a copia sincronizada do SharePoint. Sem a variavel o programa
  falha; nao ha caminho padrao perigoso.

## Instalação

`scripts/install-da-share.ps1`, distribuido em `Templates/da-share-package.zip` no vault central.

Ele confere tudo antes de escrever qualquer coisa: que o caminho e mesmo o vault central, que
existe Python no PATH e que a versao e 3.8 ou maior. A primeira versao gravava tres variaveis
de ambiente e copiava as skills **antes** de descobrir que o Python nao servia, e deixava meia
instalacao numa maquina com 3.10, onde `from datetime import UTC` nao existe.

Por isso `scripts/da_intake.py` tem piso de Python 3.8 e o piso e testado, nao comentado:
`ruff --fix` reintroduziu `datetime.UTC` em 2026-09-11 e os testes, rodando em 3.13, nao
acusaram nada. `tests/test_da_intake.py` agora falha se um construto novo demais entrar, e
`pyproject.toml` desliga UP017 so para esse arquivo.

O instalador tambem registra a tarefa **D&A Share - Friday Review**, sexta 09:00, que so abre
janela se houver algo na fila. Sem isso, a revisao depende de alguem lembrar, que e exatamente
como o fluxo de graduacao anterior morreu.

## Como medir o piloto

Os numeros que importam sao de repeticao, nao de volume:

1. Quantas pessoas distintas enviaram algo, e quantas enviaram mais de uma vez.
2. Tempo entre submissao e decisao.
3. Publicadas contra devolvidas.
4. Quantos projetos receberam atualizacao de alguem que nao e o dono.

O numero 1 e o unico que diz se virou habito. `da_intake.py queue --all --json` entrega os
quatro sem abrir o vault.
