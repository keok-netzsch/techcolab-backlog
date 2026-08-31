# Scripts de lembrete aposentados — 2026-08-30 (P3)

Estes 3 scripts foram substituídos pelo motor único `scripts/notify.ps1` + os perfis em
`scripts/notify-config.json` (decisão P3 do PM review de 2026-08-29,
`vault/pm-review-toolkit-2026-08-29.md`).

| Script | Virou o perfil |
|---|---|
| `send-morning-reminder.ps1` | `morning-reminder` |
| `send-evening-push.ps1` | `evening-push` |
| `triage-reminder.ps1` | `triage-reminder` (+ `scripts/notify-body/triage-body.ps1`) |

A migração foi **1:1**: mesmo título, mesmo texto, mesmo horário, mesmo mecanismo de
janela (MessageBox WinForms — não toast; ver o histórico de 2026-08-11 nos comentários
dos arquivos abaixo, que é a razão de o modo `messagebox` existir no motor).

Ficam aqui, e não deletados, para consulta e rollback: as tarefas agendadas podem voltar
a apontar para eles a qualquer momento se o motor der problema. Se em algumas semanas o
motor estiver estável, esta pasta pode ir embora.
