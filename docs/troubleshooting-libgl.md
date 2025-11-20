# Troubleshooting: Erro libGL.so.1

## Erro

```
ERRO CRÍTICO: DeepFace não pôde ser importado: libGL.so.1: cannot open shared object file: No such file or directory
```

## Causa

Este erro ocorre quando o `opencv-python` (versão normal) está instalado ao invés do `opencv-python-headless`. O `opencv-python` requer bibliotecas OpenGL do sistema que não estão disponíveis em ambientes headless (servidores sem interface gráfica).

## Solução Rápida

### 1. Verifique qual versão do OpenCV está instalada

```bash
pip list | grep opencv
```

### 2. Se aparecer `opencv-python`, desinstale e instale a versão headless

```bash
pip uninstall opencv-python -y
pip install opencv-python-headless
```

### 3. Reinstale todas as dependências (recomendado)

```bash
pip install -r requirements.txt
```

## Solução Completa

### Passo 1: Desinstalar opencv-python

```bash
pip uninstall opencv-python opencv-contrib-python -y
```

### Passo 2: Instalar opencv-python-headless

```bash
pip install opencv-python-headless>=4.8.0
```

### Passo 3: Verificar instalação

```python
import cv2
print(f"OpenCV versão: {cv2.__version__}")

# Tenta importar DeepFace
from deepface import DeepFace
print("✅ DeepFace importado com sucesso!")
```

## Para Streamlit Cloud

O Streamlit Cloud é um ambiente headless. Certifique-se de que:

1. O `requirements.txt` contém `opencv-python-headless` (não `opencv-python`)
2. Todas as dependências estão listadas corretamente
3. O arquivo foi commitado e pushado para o repositório

## Verificação no Código

O código já detecta automaticamente se o `opencv-python` está instalado ao invés do `opencv-python-headless` e mostra um aviso nos logs.

## Prevenção

Sempre use `opencv-python-headless` em:
- Servidores Linux
- Ambientes Docker
- Streamlit Cloud
- Qualquer ambiente sem interface gráfica

Use `opencv-python` apenas em:
- Desenvolvimento local com interface gráfica
- Aplicações desktop

## Nota

O `requirements.txt` do projeto já está configurado corretamente com `opencv-python-headless>=4.8.0`. Se você ainda receber este erro, é provável que o `opencv-python` tenha sido instalado manualmente ou por outra dependência.

