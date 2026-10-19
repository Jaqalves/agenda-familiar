# Executar no macOS

Esta é uma cópia generalizada para portfólio. Quem já usa uma versão personalizada deve manter o projeto público separado da instalação em funcionamento.

## 1. Preparar o ambiente

Requisitos: macOS, Python 3.12 e Google Chrome. O agendamento e o bloqueio de processo desta implementação usam recursos de sistemas Unix; o fluxo documentado é para macOS.

Na pasta deste projeto:

```bash
mkdir -p "$HOME/AgendaFamiliar"
python3 -m venv "$HOME/AgendaFamiliar/.venv"
"$HOME/AgendaFamiliar/.venv/bin/python" -m pip install -r requirements.txt
cp agenda_familiar.py "$HOME/AgendaFamiliar/agenda_familiar.py"
cp preferencias.example.json "$HOME/AgendaFamiliar/preferencias.json"
```

O Playwright usa o canal do Google Chrome instalado. Não há instalação automática de um navegador nesta rotina.

Edite `~/AgendaFamiliar/preferencias.json`: coloque o nome exato do grupo, uma consulta de busca e a saudação desejada. Crie o grupo no WhatsApp e confira os participantes antes do teste. Se alterar o nome do grupo, altere a configuração e faça novo teste antes de reagendar.

## 2. Configurar o Google Calendar

No Google Cloud, crie ou selecione um projeto, habilite a Google Calendar API, configure o consentimento OAuth e crie um cliente OAuth do tipo **Aplicativo para computador**. Baixe o JSON desse cliente e salve como `~/Downloads/credentials.json`.

```bash
"$HOME/AgendaFamiliar/.venv/bin/python" "$HOME/AgendaFamiliar/agenda_familiar.py" autorizar
"$HOME/AgendaFamiliar/.venv/bin/python" "$HOME/AgendaFamiliar/agenda_familiar.py" configurar
```

A configuração OAuth deve ser adequada ao uso contínuo. O estado de testes do Google pode limitar a duração da autorização; siga a documentação oficial e as exigências apresentadas no seu projeto.

- [Guia oficial de Python e Google Calendar](https://developers.google.com/workspace/calendar/api/quickstart/python)
- [Estados de publicação e verificação OAuth](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview)

### Tratamento dos calendários

| Modo | Comportamento |
| --- | --- |
| F | Permite detalhes familiares; eventos privados ou confidenciais continuam ocultos |
| P | Usa “Compromisso profissional”, sem descrição ou local |
| M | Revela detalhes apenas de eventos com `[familia]` no título, respeitando a privacidade do evento |
| I | Ignora o calendário |

Um calendário novo e ainda não classificado bloqueia o envio até nova configuração.

## 3. Prévia e teste no WhatsApp

```bash
"$HOME/AgendaFamiliar/.venv/bin/python" "$HOME/AgendaFamiliar/agenda_familiar.py" previa
"$HOME/AgendaFamiliar/.venv/bin/python" "$HOME/AgendaFamiliar/agenda_familiar.py" enviar
```

No primeiro acesso ao WhatsApp Web, use o QR code para autenticar o perfil aberto pelo programa. Conclua o login dentro do tempo de espera ou rode novamente após autenticar. Deixe a janela aberta até a execução terminar. O comando `enviar` realiza um envio real ao grupo configurado.

Se houver erro após o clique, confira a conversa e os registros antes de tentar novamente. `conferir` é somente leitura; `recuperar` pode enviar um rascunho idêntico ao resumo atual, quando as verificações permitirem.

## 4. Agendar

Somente depois da confirmação do teste no grupo:

```bash
"$HOME/AgendaFamiliar/.venv/bin/python" "$HOME/AgendaFamiliar/agenda_familiar.py" ativar
```

O agendamento começa no dia seguinte, todos os dias, às 07h10 de Brasília. O Terminal pode ser fechado. O Mac precisa permanecer acordado, com o usuário conectado e internet. A rotina não configura o despertar do computador.

Para desligar a rotina:

```bash
"$HOME/AgendaFamiliar/.venv/bin/python" "$HOME/AgendaFamiliar/agenda_familiar.py" desativar
```

## Arquivos locais

Todos os dados de execução ficam em `~/AgendaFamiliar`, incluindo token, preferências, classificação de calendários, perfil do navegador, prévia e registros. Proteja essa pasta e não a publique. Os arquivos `rotina.log` e `erros.log` ajudam a verificar falhas. A aplicação usa o cliente OAuth guardado em Downloads para renovar a autorização inicial quando solicitado.

As dependências de `requirements.txt` não estão fixadas por versão. Mudanças em bibliotecas e na interface do WhatsApp podem exigir nova validação.
