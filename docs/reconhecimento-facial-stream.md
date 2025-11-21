# Reconhecimento Facial com Stream de Vídeo em Tempo Real

## 📹 Visão Geral

O sistema agora suporta **duas modalidades** de reconhecimento facial:

1. **🎥 Vídeo em Tempo Real (Stream)** - RECOMENDADO
   - Pessoa **apenas passa pela câmera**
   - Reconhecimento **automático e instantâneo**
   - Ideal para **controle de acesso de portaria**

2. **📸 Foto Estática**
   - Pessoa **tira uma foto manualmente**
   - Reconhecimento após captura
   - Ideal para **cadastro e situações pontuais**

## 🎥 Modo Vídeo Stream (Padrão)

### Como Funciona

1. Sistema inicia câmera em **modo vídeo contínuo**
2. Pessoa **passa naturalmente** pela frente da câmera
3. Sistema **detecta e reconhece** automaticamente
4. **Acesso liberado/negado** instantaneamente
5. Display mostra **caixa verde** (liberado) ou **vermelha** (negado)

### Características Técnicas

- **Processamento:** 1 frame a cada 5 (otimização de CPU)
- **Cooldown:** 5 segundos entre reconhecimentos (evita duplicatas)
- **Latência:** ~200ms para reconhecimento
- **Taxa de quadros:** 15-20 FPS (adaptável)
- **Resolução:** 1280x720 (ideal para reconhecimento)

### Uso no Sistema

#### Acesso Autenticado (Portaria)
```bash
# Inicie o sistema normalmente
streamlit run main.py

# No menu lateral, selecione:
"🎥 Acesso por Vídeo (Stream)"
```

#### Acesso Público (Terminal de Entrada)
```bash
# Execute o arquivo de acesso público
streamlit run public_access.py

# OU acesse via navegador:
http://localhost:8501/?public=true&video=true
```

### Configurações Avançadas

```python
# Em app/face_access_stream.py ou app/public_face_access_stream.py

# Ajustar cooldown entre reconhecimentos (segundos)
self.recognition_cooldown = 5  # Padrão: 5 segundos

# Ajustar quantos frames pular (otimização)
self.process_every_n_frames = 5  # Padrão: 5 (processa 1 a cada 5)

# Ajustar threshold de reconhecimento (similaridade)
threshold = 0.4  # Padrão: 0.4 (menor = mais rigoroso)
```

## 📸 Modo Foto (Alternativo)

### Como Funciona

1. Pessoa clica para **tirar foto**
2. Sistema processa **imagem única**
3. Reconhecimento após captura
4. Acesso liberado/negado manualmente

### Uso no Sistema

#### Acesso Autenticado
```bash
streamlit run main.py
# Selecione: "Acesso por Foto"
```

#### Acesso Público
```bash
# Via URL com parâmetro
http://localhost:8501/?public=true&video=false

# OU execute main.py com query params
streamlit run main.py -- --public=true --video=false
```

## 🔧 Tecnologias Utilizadas

### Para Stream de Vídeo

| Componente | Biblioteca | Função |
|------------|-----------|---------|
| **Captura de Vídeo** | `streamlit-webrtc` | Streaming via WebRTC |
| **Processamento Vídeo** | `aiortc` | Protocolo RTC para tempo real |
| **Reconhecimento** | `InsightFace` (buffalo_s) | Detecção e embedding facial |
| **Engine** | `ONNX Runtime` | Processamento otimizado CPU |

### Arquitetura do Stream

```
┌─────────────────────────────────────────────────────────────┐
│                     Câmera do Navegador                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebRTC Stream
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  streamlit-webrtc                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │  video_frame_callback (processa frame a frame)      │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────┬──────────────────────────────────────┘
                       │ Frame BGR (OpenCV)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               InsightFace + ONNX Runtime                    │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ Detecção (SCRFD) │  │ Embedding (ArcFace)│              │
│  └──────────────────┘  └──────────────────┘               │
└──────────────────────┬──────────────────────────────────────┘
                       │ Embedding + BBox
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            Comparação com Banco de Dados                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Busca pessoa com menor distância cosseno          │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────┬──────────────────────────────────────┘
                       │ Pessoa reconhecida
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Registro de Acesso (Async)                     │
│  - Verifica bloqueios                                       │
│  - Registra no Supabase                                     │
│  - Atualiza display (caixa verde/vermelha)                 │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Otimizações para Streamlit Cloud

### 1. Processamento Assíncrono
- Frames processados em background
- Registro no banco em thread separada
- Interface nunca trava

### 2. Otimização de CPU
```python
# Processa apenas 1 frame a cada 5
if face_state.frame_count % 5 != 0:
    return frame  # Pula processamento

# Usa ONNX Runtime (CPU otimizado)
providers=['CPUExecutionProvider']

# Modelo leve (buffalo_s ao invés de buffalo_l)
name='buffalo_s'
```

### 3. Cooldown Inteligente
```python
# Evita processar mesma pessoa várias vezes
if time_since_last < cooldown:
    skip_processing()
```

## 📊 Performance Esperada

### No Streamlit Cloud (Free Tier)

| Métrica | Valor Esperado |
|---------|---------------|
| **FPS (com processamento)** | 3-5 FPS |
| **FPS (sem processamento)** | 15-20 FPS |
| **Latência de reconhecimento** | 200-500ms |
| **Uso de memória** | 500-800 MB |
| **Uso de CPU** | 40-60% |

### Em Servidor Dedicado (1 vCPU, 2GB RAM)

| Métrica | Valor Esperado |
|---------|---------------|
| **FPS (com processamento)** | 5-10 FPS |
| **FPS (sem processamento)** | 25-30 FPS |
| **Latência de reconhecimento** | 100-300ms |
| **Uso de memória** | 600-1000 MB |
| **Uso de CPU** | 30-50% |

## 🎯 Quando Usar Cada Modo

### Use **Vídeo Stream** quando:
- ✅ Controle de acesso de **portaria/catraca**
- ✅ Fluxo **contínuo de pessoas**
- ✅ Precisa de **reconhecimento automático**
- ✅ Ambiente **controlado** (iluminação boa)
- ✅ Terminal **dedicado** (tablet/PC fixo)

### Use **Foto** quando:
- ✅ **Cadastro** de novas pessoas
- ✅ **Verificação pontual**
- ✅ Ambiente com **iluminação variável**
- ✅ Pessoa **não familiarizada** com o sistema
- ✅ Necessário **revisar** imagem antes de processar

## 🔒 Segurança

### Cooldown de Reconhecimento
- Evita registros duplicados
- Pessoa reconhecida fica em "cooldown" por 5 segundos
- Após cooldown, pode ser reconhecida novamente

### Validação de Bloqueios
- Verificação em **tempo real** no banco
- Lista de bloqueios atualizada automaticamente
- Tentativas de acesso bloqueado são **registradas**

### Threshold de Similaridade
- Padrão: **0.4** (distância cosseno)
- Valores menores = mais rigoroso
- Ajustável conforme taxa de falsos positivos

## 📱 Compatibilidade

### Navegadores Suportados

| Navegador | Desktop | Mobile | Notas |
|-----------|---------|--------|-------|
| **Chrome** | ✅ | ✅ | Recomendado |
| **Edge** | ✅ | ✅ | Chromium-based |
| **Firefox** | ✅ | ⚠️ | Pode ter latência maior |
| **Safari** | ⚠️ | ⚠️ | WebRTC limitado |

### Recomendações
- Use **Chrome** ou **Edge** para melhor performance
- Permita acesso à **câmera** quando solicitado
- Conexão de internet **estável** (para Streamlit Cloud)
- Iluminação **frontal** (evite contraluz)

## 🐛 Troubleshooting

### "Câmera não inicia"
```bash
# Verifique permissões do navegador
# Chrome: chrome://settings/content/camera
# Tente outro navegador
# Verifique se outra aplicação está usando a câmera
```

### "Reconhecimento muito lento"
```python
# Aumente o intervalo de processamento
self.process_every_n_frames = 10  # Processa menos frames

# OU reduza resolução
"width": {"ideal": 640},  # Ao invés de 1280
"height": {"ideal": 480},  # Ao invés de 720
```

### "Muitos falsos positivos"
```python
# Reduza o threshold (mais rigoroso)
threshold = 0.3  # Ao invés de 0.4
```

### "Muitos falsos negativos"
```python
# Aumente o threshold (mais tolerante)
threshold = 0.5  # Ao invés de 0.4
```

## 📝 Notas Importantes

1. **Primeira execução**: Modelo buffalo_s é baixado automaticamente (~60MB)
2. **Latência inicial**: Primeiro reconhecimento pode ser mais lento (carregamento do modelo)
3. **Uso de dados**: Stream de vídeo consome ~2-5 MB/min de dados
4. **Privacidade**: Vídeo é processado localmente, não é armazenado
5. **Compatibilidade RLS**: Sistema respeita políticas RLS do Supabase

## 🔄 Migração de Foto → Stream

Se você já tem o sistema rodando com **foto**, para migrar para **stream**:

1. Instale novas dependências:
```bash
pip install -r requirements.txt
```

2. Acesse a nova página de stream:
```bash
# No menu lateral
"🎥 Acesso por Vídeo (Stream)"
```

3. **Nenhuma ação adicional necessária!**
   - Embeddings existentes são compatíveis
   - Threshold e configurações mantidos
   - Pessoas já cadastradas funcionam imediatamente

## 📚 Referências

- [InsightFace Documentation](https://github.com/deepinsight/insightface)
- [Streamlit WebRTC](https://github.com/whitphx/streamlit-webrtc)
- [ONNX Runtime](https://onnxruntime.ai/)
- [WebRTC Standard](https://webrtc.org/)

