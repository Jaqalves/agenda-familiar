# Seu primeiro repositório no GitHub

Um **repositório** é a pasta do projeto no GitHub. O **README** é sua apresentação. Um **commit** é um registro de uma versão dos arquivos.

## Publicar pelo navegador

1. Entre na sua conta e abra https://github.com/new.
2. Em **Repository name**, use `agenda-familiar`.
3. Em **Description**, use: `Automação em Python que consolida o Google Calendar e envia a agenda familiar pelo WhatsApp, com regras de privacidade e agendamento no macOS.`
4. Para mostrar no portfólio, escolha **Public**. Revise os arquivos antes de confirmar, pois eles ficarão visíveis ao público.
5. Deixe desmarcada a criação automática de README, .gitignore e licença: o pacote já contém README e .gitignore; a escolha de uma licença pode ser feita depois.
6. Clique em **Create repository**.
7. Na página do repositório vazio, clique em **uploading an existing file**. Se o repositório já tiver arquivos, use **Add file → Upload files**.
8. Extraia o ZIP preparado para o portfólio e envie o **conteúdo** da pasta `agenda-familiar`, preservando as subpastas. Não envie o ZIP como único arquivo.
9. No macOS, use `Command + Shift + .` no Finder para visualizar `.gitignore` e a pasta `.github`, se necessário. Confira se esses arquivos também foram incluídos.
10. Em **Commit changes**, escreva `Adiciona projeto Agenda Familiar` e confirme.

Depois de publicar, a página principal deve mostrar o texto do README e os diretórios `docs`, `examples` e `tests`. A pasta `.github` contém a verificação automática dos testes. Ela verifica o código; não executa o envio diário.

## Destacar no perfil

No seu perfil, use **Customize your pins** para destacar o repositório, se essa opção estiver disponível. Adicione tópicos como `python`, `automation`, `google-calendar`, `playwright` e `portfolio` na seção **About** do repositório.

## O que deve ficar fora

Publique apenas a cópia generalizada deste pacote. Não envie a pasta `~/AgendaFamiliar`, `credentials.json`, `token.json`, o perfil do WhatsApp, logs ou capturas de conversas reais. O `.gitignore` ajuda no uso de Git, mas não substitui a conferência dos arquivos que você seleciona manualmente no navegador.

Não há credenciais no pacote e nenhum dado real é necessário para apresentar o projeto.

## Referências oficiais

- [Criar um repositório](https://docs.github.com/pt/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [Adicionar arquivos](https://docs.github.com/pt/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
