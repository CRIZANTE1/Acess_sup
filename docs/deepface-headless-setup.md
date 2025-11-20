# Configuração do DeepFace em Ambientes Headless (Linux sem Interface Gráfica)

## Problema

O erro `libGL.so.1: cannot open shared object file: No such file or directory` ocorre quando o DeepFace/OpenCV tenta usar bibliotecas OpenGL que não estão disponíveis em ambientes Linux sem interface gráfica (headless).

## Soluções

### Opção 1: Instalar Bibliotecas do Sistema (Recomendado)

#### Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1
```

#### CentOS/RHEL:
```bash
sudo yum install -y mesa-libGL mesa-libGL-devel glib2 libSM libXext libXrender libgomp
```

#### Alpine Linux (Docker):
```bash
apk add --no-cache libgl libglib mesa-gl
```

### Opção 2: Usar Docker com Imagem que Já Inclui as Bibliotecas

Se estiver usando Docker, use uma imagem base que já inclui as bibliotecas gráficas:

```dockerfile
FROM python:3.11-slim

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Resto da configuração...
```

### Opção 3: Configurar Variáveis de Ambiente (Já Implementado)

O código já configura automaticamente as variáveis de ambiente necessárias:
- `QT_QPA_PLATFORM=offscreen`
- `DISPLAY=:0`
- `OPENCV_IO_ENABLE_OPENEXR=0`

### Opção 4: Usar OpenCV Headless (Alternativa)

Se as soluções acima não funcionarem, você pode tentar usar a versão headless do OpenCV:

```bash
pip uninstall opencv-python
pip install opencv-python-headless
```

**Nota:** `opencv-python-headless` pode não ter todas as funcionalidades do `opencv-python`, mas geralmente funciona bem para reconhecimento facial.

## Verificação

Para verificar se o problema foi resolvido:

```python
import cv2
print(cv2.__version__)  # Deve imprimir a versão sem erros

from deepface import DeepFace
print("DeepFace importado com sucesso!")
```

## Para Streamlit Cloud

O Streamlit Cloud geralmente já tem as bibliotecas necessárias, mas se o erro persistir:

1. Verifique os logs para ver se há mensagens sobre bibliotecas faltando
2. Considere usar `opencv-python-headless` em vez de `opencv-python`
3. Adicione as bibliotecas do sistema via `packages.txt` (se suportado)

## Nota Importante

O código já trata esses erros graciosamente. Se o DeepFace não puder ser importado, o sistema continuará funcionando, mas a funcionalidade de reconhecimento facial ficará desabilitada até que as dependências sejam instaladas corretamente.

