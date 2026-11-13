# Monitor de Carros → Telegram

Todo dia às 08:00 este robô procura carros de **R$ 15.000 a R$ 35.000** num raio de
**50 km de Parobé/RS** e te manda no Telegram **só os anúncios novos** e os que
**baixaram de preço**. Roda de graça na nuvem (GitHub Actions), sem precisar do PC ligado.

**Fontes:** Mobiauto, NaPista e Chaves na Mão. O mesmo carro anunciado em mais de
um site aparece uma vez só, com os links de todos.

> OLX, Webmotors e Mercado Livre bloqueiam acesso automatizado, e o iCarros
> desativou os classificados. Por isso esses sites ficaram de fora.

---

## Configuração (uma vez só, ~15 minutos)

### 1. Criar o bot no Telegram
1. No Telegram, abra uma conversa com **@BotFather** e mande `/newbot`.
2. Escolha um nome e um usuário para o bot (o usuário precisa terminar em `bot`).
3. O BotFather responde com um **token** parecido com `123456789:AAH...`. Guarde-o.
4. Abra a conversa com o **seu** bot novo e mande qualquer mensagem (ex.: `oi`).
5. No navegador, abra `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
   (troque `<SEU_TOKEN>` pelo token). Procure `"chat":{"id":123456789` e anote
   esse número: é o seu **CHAT_ID**.

### 2. Colocar o projeto no GitHub
1. Crie uma conta em <https://github.com> (se ainda não tiver).
2. Crie um repositório novo (**New repository**), por exemplo `monitor-carros`.
   Pode ser **Private**. Não marque nenhuma opção de README/gitignore.
3. Nesta pasta, rode (trocando `SEU_USUARIO`):
   ```bash
   git init
   git add .
   git commit -m "Monitor de carros"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/monitor-carros.git
   git push -u origin main
   ```

### 3. Guardar o token como segredo no GitHub
No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
Crie dois segredos:

| Nome | Valor |
|---|---|
| `TELEGRAM_TOKEN` | o token do BotFather |
| `TELEGRAM_CHAT_ID` | o número do passo 1.5 |

### 4. Testar
Vá em **Actions → Monitor de carros diário → Run workflow**. Em ~5 minutos a
mensagem chega no Telegram. Depois disso ele roda sozinho todo dia.

> Na **primeira** execução todos os anúncios atuais são "novos", então vêm os
> 40 mais baratos. Do segundo dia em diante chegam só as novidades.

---

## Como mudar a busca
Edite o [config.toml](config.toml) (dá para editar direto no site do GitHub, no
ícone de lápis) e salve com commit:

- `preco_min` / `preco_max`: faixa de preço
- `cidade_centro` / `raio_km`: região (qualquer cidade do RS)
- `ano_min`: ano mínimo
- `modelos`: ex. `["gol", "onix", "hb20"]` para receber só esses modelos
- `palavras_excluir`: descarta anúncios com essas palavras no título
- `max_por_dia`: limite de carros por mensagem diária

Se mudar muito a região, ajuste também `cidades_polo` da Mobiauto.

## Horário
O horário está em [.github/workflows/diario.yml](.github/workflows/diario.yml), no formato
cron e em **UTC** (Brasília = UTC−3). `45 10 * * *` = 07:45, para chegar por volta
das 08:00. O GitHub às vezes atrasa a execução agendada em 10 a 30 minutos.

## Rodar no seu PC (opcional)
```bash
pip install -r requirements.txt
python main.py --teste
```
O `--teste` só mostra o resultado no terminal: não envia nada e não salva o histórico.

## Se algo quebrar
Os sites mudam de layout de vez em quando. Quando uma fonte falha, a mensagem do
dia avisa ("⚠️ Fontes com problema hoje"), e as outras fontes continuam
funcionando. Se todas falharem, o GitHub te manda um e-mail. O código de cada site
fica em `fontes/`.

## Arquivos
- `main.py`: junta as fontes, filtra, compara com o histórico e envia
- `fontes/`: um arquivo por site
- `cidades.py` + `dados/municipios_rs.csv`: coordenadas das cidades do RS, usadas para calcular a distância
- `dados/vistos.json`: histórico de anúncios já enviados (atualizado sozinho pelo robô)
- `bot_carros.py`: rascunho antigo (só Webmotors), não é mais usado
