# Backblaze B2 para os arquivos das publica��es

O banco de dados e as contas continuam no backend atual. Com B2 configurado, novos quadrinhos e capas s�o enviados para o bucket privado. A API do Komicove continua verificando as permiss�es antes de servir os arquivos. Arquivos antigos ainda podem ser lidos do Supabase Storage se a configura��o anterior continuar dispon�vel.

Configure as seguintes vari�veis **somente no servidor da API**:

```text
B2_ENDPOINT=https://s3.us-east-005.backblazeb2.com
B2_BUCKET=komicove-assets-luanz
B2_KEY_ID=<ID da Application Key>
B2_APPLICATION_KEY=<Application Key>
```

Use uma Application Key limitada ao bucket, com acesso Read and Write. N�o use a Master Application Key. N�o coloque essas credenciais no aplicativo desktop, Android, no Git ou em vari�veis p�blicas do frontend. Configure as vari�veis no ambiente do processo da API ou no painel de ambiente da hospedagem. O backend n�o carrega `.env` automaticamente.

Instale as depend�ncias do servidor com `python -m pip install -e ".[server]"` ou `python -m pip install -r requirements.txt` e reinicie a API. O endpoint do exemplo � da regi�o US East 005; se o bucket estiver em outra regi�o, use o endpoint exibido na p�gina dele.

Antes de retirar as vari�veis `SUPABASE_URL`, `SUPABASE_SECRET_KEY` e `SUPABASE_BUCKET`, migre ou mantenha acess�veis os arquivos de publica��es antigas que estiverem apenas no Supabase Storage. Remover a configura��o anterior cedo demais impediria o download desses arquivos em uma inst�ncia sem cache local.
