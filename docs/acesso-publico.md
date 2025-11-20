# Acesso Público por Reconhecimento Facial

## Visão Geral

O sistema possui uma página **pública** de acesso por reconhecimento facial, onde qualquer pessoa pode acessar sem necessidade de login. A pessoa tira uma foto, o sistema reconhece automaticamente e libera ou bloqueia o acesso.

## Como Acessar

### Opção 1: Via Query Parameter
Acesse a URL com o parâmetro `public=true`:
```
http://localhost:8501/?public=true
```

### Opção 2: Arquivo Dedicado
Execute o arquivo `public_access.py`:
```bash
streamlit run public_access.py
```

## Funcionamento

### Fluxo do Sistema

1. **Pessoa acessa a página pública**
   - Não precisa fazer login
   - Interface simples e direta

2. **Tira foto via câmera web**
   - Usa `st.camera_input` do Streamlit
   - Foto capturada diretamente da câmera

3. **Sistema processa reconhecimento**
   - Usa DeepFace (Google FaceNet)
   - Compara com pessoas cadastradas
   - Threshold: 0.4 (configurável)

4. **Resultado:**
   - ✅ **Reconhecida e Liberada**: Entrada registrada automaticamente
   - 🚫 **Reconhecida e Bloqueada**: Acesso negado (está na blocklist)
   - ⚠️ **Não Reconhecida**: Pessoa não cadastrada

### Cenários de Acesso

#### ✅ Pessoa Reconhecida e Liberada
- Sistema encontra correspondência no banco
- Verifica se está na blocklist
- Se não estiver bloqueada → **ACESSO LIBERADO**
- Registra entrada automaticamente
- Mostra informações do acesso (horário, data, empresa)

#### 🚫 Pessoa Reconhecida e Bloqueada
- Sistema encontra correspondência no banco
- Verifica blocklist → **ESTÁ BLOQUEADA**
- **ACESSO NEGADO**
- Registra tentativa de acesso bloqueado
- Mostra motivo do bloqueio

#### ⚠️ Pessoa Não Reconhecida
- Sistema não encontra correspondência
- **PESSOA NÃO RECONHECIDA**
- Não registra entrada
- Orienta a pessoa a entrar em contato com portaria

## Segurança

### Verificações Implementadas
1. **Reconhecimento Facial**: Valida identidade via DeepFace
2. **Blocklist**: Verifica se pessoa/empresa está bloqueada
3. **Logs**: Todas as tentativas são registradas
4. **Threshold**: Configurável para maior/menor rigor

### Registros Automáticos
- Todas as tentativas de acesso são registradas
- Status: "Autorizado", "Bloqueado" ou não registrado (não reconhecida)
- Aprovador: "Sistema Automático (Reconhecimento Facial)"

## Interface

### Design
- Layout centralizado e limpo
- Título grande: "ACESSO BAERI"
- Câmera web integrada
- Feedback visual claro:
  - 🟢 Verde para acesso liberado
  - 🔴 Vermelho para acesso negado
  - 🟡 Amarelo para não reconhecida

### Elementos Visuais
- **Balloons** quando acesso é liberado
- Mensagens grandes e claras
- Informações do acesso após liberação
- Dicas de uso colapsáveis

## Configuração

### Variáveis de Ambiente
Nenhuma configuração adicional necessária. Usa as mesmas credenciais do Supabase.

### Threshold de Reconhecimento
Pode ser ajustado no código:
```python
result = find_matching_person(picture, db_ops, threshold=0.4)
```
- **Menor** (ex: 0.3) = Mais rigoroso
- **Maior** (ex: 0.5) = Menos rigoroso

## Uso em Produção

### Para Deploy
1. Configure o Supabase Storage para fotos
2. Certifique-se de que as políticas RLS estão corretas
3. Acesse via: `https://seu-app.streamlit.app/?public=true`

### Recomendações
- Use em dispositivo com câmera (tablet, computador)
- Boa iluminação no local
- Câmera posicionada na altura do rosto
- Conexão estável com internet

## Troubleshooting

### Câmera não aparece
- Verifique permissões do navegador
- Use HTTPS em produção (requerido para câmera)

### Reconhecimento não funciona
- Verifique se DeepFace está instalado
- Confirme que há pessoas cadastradas com foto
- Verifique qualidade da foto capturada

### Acesso sempre negado
- Verifique threshold (pode estar muito baixo)
- Confirme que a pessoa está cadastrada
- Verifique se não está na blocklist

