# Agenda Familiar

**Do calendário à mensagem: uma rotina diária para organizar os próximos dois dias.**

Projeto pessoal que consulta calendários selecionados no Google Calendar, consolida compromissos de hoje e amanhã e envia um resumo a um grupo autorizado no WhatsApp Web.

Python · Google Calendar API · OAuth 2.0 · Playwright · macOS / launchd

## O problema

Compromissos distribuídos em calendários pessoais, profissionais e compartilhados exigem consultas repetidas e comunicação manual. A proposta é transformar essas fontes em uma mensagem única, com horários, observações permitidas e pontos de atenção.

## A solução

A rotina consulta dados atualizados, aplica regras de organização e privacidade, prepara o resumo e realiza um único envio diário ao grupo configurado. A autorização do Google é somente de leitura.

| Etapa | Responsabilidade |
| --- | --- |
| Consultar | Listar calendários visíveis, consultar eventos e disponibilidade |
| Consolidar | Ordenar, deduplicar e tratar cancelamentos, recusas e dia inteiro |
| Proteger | Aplicar regras por calendário e ocultar detalhes privados |
| Comunicar | Gerar mensagem e verificar grupo e confirmação do WhatsApp |
| Agendar | Executar diariamente no Mac às 07h10 de Brasília |

## Demonstração

O arquivo [mensagem_exemplo.txt](examples/mensagem_exemplo.txt) usa **dados inteiramente fictícios**. Não contém dados reais de agenda ou de destinatários.

```text
☀️ *BOM DIA, FAMÍLIA!*

📅 *AGENDA DE HOJE — SEGUNDA-FEIRA, 19/10/2026*
🕒 08h00 — Atividade de exemplo

📆 *AMANHÃ — TERÇA-FEIRA, 20/10/2026*
Não há compromissos registrados.
```

O formato completo inclui observações permitidas, possíveis deslocamentos, conflitos e um resumo dos períodos com mais inícios de compromissos.

## Decisões de implementação

- **Sem IA em tempo de execução:** a consolidação e o texto usam regras determinísticas em Python. O projeto foi desenvolvido com assistência de IA.
- **Menor permissão:** o escopo `calendar.readonly` permite consultar, sem criar ou alterar eventos.
- **Privacidade por calendário:** familiar, profissional, misto ou ignorado.
- **Sem reenvio automático após um clique incerto:** um registro é gravado antes de clicar em Enviar. Uma tentativa interrompida exige conferência.
- **Confirmação observável:** somente marca de envio reconhecida na interface permite registrar sucesso; isso não comprova leitura por todos os participantes.
- **Grupo exato:** a seleção exige o título configurado e a abertura de Dados do grupo. Ambiguidade interrompe a operação.

## Instalação e uso

Veja [como executar no macOS](docs/INSTALACAO.md). O padrão do programa é gerar uma prévia; o envio e o agendamento são ações explícitas.

| Comando | Efeito |
| --- | --- |
| `autorizar` | Autoriza o acesso Google e salva o token local |
| `configurar` | Define o tratamento de cada calendário |
| `previa` | Consulta a agenda e mostra a mensagem sem enviar |
| `enviar` | Envia ao grupo configurado, após verificações |
| `conferir` | Procura a mensagem de hoje sem enviar |
| `recuperar` | Tenta recuperar uma execução incerta; pode enviar um rascunho idêntico após verificações |
| `status` | Mostra os registros de envio |
| `ativar` | Registra a rotina diária após um teste confirmado no grupo |
| `desativar` | Remove o agendamento local |

## Agendamento e limites

O LaunchAgent verifica o horário periodicamente. A janela de execução é **07h10 a 07h14 em America/Sao_Paulo**, com no máximo uma tentativa automática por dia. O agendamento começa no dia seguinte à ativação e inclui fins de semana e feriados.

O Mac deve estar ligado, acordado, com o usuário conectado, internet e sessões válidas. Não há recuperação tardia após 07h14. A rotina não é hospedada no GitHub: publicar o código não executa o programa nem transfere as credenciais.

A integração com WhatsApp usa automação da interface Web, não a API oficial de mensagens. Mudanças na interface podem exigir manutenção. A conferência percorre um número limitado de trechos do histórico; a prevenção de duplicações depende também dos arquivos locais e de preservar o mesmo perfil. Não é uma garantia transacional de entrega exatamente uma vez.

## Testes e validação

```bash
python3 -m unittest discover -s tests -v
```

Os testes públicos cobrem regras de confidencialidade, eventos recusados e cancelados, dia inteiro e bloqueio de calendários desconhecidos. Não acessam contas, não abrem o WhatsApp e não enviam mensagens.

A versão personalizada de origem teve um envio real ao grupo confirmado pela interface e o agendamento local registrado. A versão pública foi generalizada e validada localmente; precisa de configuração e teste próprios. A operação automática contínua ainda não foi medida, e não são alegadas métricas de tempo economizado ou taxa de entrega.

## Aprendizados

1. Separar intenção de enviar, clique realizado e confirmação observável evita tratar uma tentativa como sucesso.
2. Conversas virtualizadas exigem considerar que mensagens antigas podem não estar no DOM.
3. Emojis podem ser imagens na interface e precisam de tratamento ao comparar texto.
4. Regras de confidencialidade devem ser aplicadas antes de gerar a mensagem.
5. Testes locais não substituem a validação da integração com serviços reais.

## Próximas evoluções

- Extrair módulos de calendário, formatação, envio e agendamento do script principal.
- Ampliar os testes de integração e registrar evidências de uma sequência de execuções automáticas.
- Melhorar a navegação por histórico e a identificação estável do grupo.
- Avaliar um canal com API oficial para cenários que exijam maior previsibilidade.
- Gerar um arquivo de dependências com versões fixadas após validar um ambiente de reprodução.

## Publicar seu primeiro repositório

Há um [passo a passo pelo navegador](docs/GITHUB_PRIMEIROS_PASSOS.md), sem necessidade de usar Git no Terminal.

**Autoria:** Jaqueline Alves, com desenvolvimento assistido por IA e validação prática.
