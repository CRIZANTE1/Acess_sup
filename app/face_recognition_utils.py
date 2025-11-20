"""
Módulo para processamento e reconhecimento facial usando DeepFace
"""
import streamlit as st
import json
from typing import Optional, Tuple, List
import io
import logging
import os

logging.basicConfig(level=logging.ERROR)

# ============================================
# CONFIGURAÇÃO PARA AMBIENTES HEADLESS (Linux sem interface gráfica)
# ============================================
# Configura variáveis de ambiente ANTES de importar OpenCV/DeepFace
# Isso evita o erro "libGL.so.1: cannot open shared object file"
# IMPORTANTE: Estas variáveis DEVEM ser configuradas ANTES de qualquer importação

# Desabilita OpenGL e interface gráfica
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['DISPLAY'] = ':0'
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '0'
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
# Força OpenCV a não usar GUI
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
# Desabilita threading que pode causar problemas
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

# Tenta configurar OpenCV antes de importar DeepFace
# Isso garante que o OpenCV seja configurado corretamente
try:
    # Tenta importar cv2 (deve ser opencv-python-headless, não opencv-python)
    import cv2
    # Desabilita threading que pode causar problemas
    try:
        cv2.setNumThreads(1)
    except:
        pass
    # Tenta usar backend sem OpenGL
    try:
        cv2.setUseOptimized(False)
    except:
        pass
    # Verifica se é opencv-python-headless (não tem GUI)
    try:
        # Se conseguir criar uma janela, não é headless
        cv2.namedWindow('test', cv2.WINDOW_NORMAL)
        cv2.destroyWindow('test')
        logging.warning("⚠️ opencv-python está instalado ao invés de opencv-python-headless")
        logging.warning("   Desinstale opencv-python e instale opencv-python-headless")
    except:
        # Não conseguiu criar janela = headless (correto)
        pass
except ImportError:
    # OpenCV não está instalado ainda, mas as variáveis de ambiente já estão configuradas
    pass
except Exception as e:
    # Se houver erro ao configurar OpenCV, continua mesmo assim
    logging.warning(f"Aviso ao configurar OpenCV: {e}")

# Imports opcionais com tratamento de erro
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None
    logging.error("❌ numpy não está instalado. Instale com: pip install numpy")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    logging.error("❌ Pillow não está instalado. Instale com: pip install Pillow")

try:
    # Tenta importar DeepFace - ESSENCIAL para reconhecimento facial
    # As variáveis de ambiente já foram configuradas acima para evitar erro libGL
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    logging.info("DeepFace importado com sucesso")
except ImportError as e:
    DEEPFACE_AVAILABLE = False
    DeepFace = None
    logging.error(f"❌ ERRO CRÍTICO: DeepFace não pôde ser importado: {e}")
    logging.error("")
    logging.error("🔧 Para instalar, execute:")
    logging.error("   pip install deepface opencv-python-headless tensorflow numpy Pillow")
    logging.error("")
    logging.error("⚠️ IMPORTANTE: Use opencv-python-headless (não opencv-python) em servidores")
except OSError as e:
    # Erro específico de biblioteca do sistema (ex: libGL.so.1)
    DEEPFACE_AVAILABLE = False
    DeepFace = None
    error_msg = str(e)
    if 'libGL' in error_msg or 'libgthread' in error_msg:
        logging.error(f"❌ ERRO: Biblioteca do sistema não encontrada: {e}")
        logging.error("")
        logging.error("🔧 SOLUÇÕES POSSÍVEIS:")
        logging.error("")
        logging.error("1️⃣ DESINSTALE opencv-python e INSTALE opencv-python-headless:")
        logging.error("   pip uninstall opencv-python -y")
        logging.error("   pip install opencv-python-headless")
        logging.error("")
        logging.error("2️⃣ OU instale as bibliotecas do sistema (Linux):")
        logging.error("   Ubuntu/Debian: sudo apt-get install -y libgl1-mesa-glx libglib2.0-0")
        logging.error("   CentOS/RHEL: sudo yum install -y mesa-libGL mesa-libGL-devel glib2")
        logging.error("")
        logging.error("3️⃣ OU use Docker com imagem que já inclui essas bibliotecas")
        logging.error("")
        logging.error("⚠️ IMPORTANTE: Use opencv-python-headless em ambientes headless (servidores)")
    else:
        logging.error(f"ERRO ao importar DeepFace: {e}")
except Exception as e:
    DEEPFACE_AVAILABLE = False
    DeepFace = None
    logging.error(f"ERRO ao importar DeepFace: {e}")

try:
    import cv2
    CV2_AVAILABLE = True
except (ImportError, Exception) as e:
    CV2_AVAILABLE = False
    cv2 = None
    logging.warning(f"opencv-python não está disponível: {e}")


# Configuração do modelo DeepFace
# Opções: VGG-Face, Facenet, OpenFace, DeepFace, DeepID, Dlib, ArcFace
DEEPFACE_MODEL = os.getenv('DEEPFACE_MODEL', 'Facenet')  # Usa Google FaceNet por padrão
DEEPFACE_BACKEND = os.getenv('DEEPFACE_BACKEND', 'opencv')  # opencv, ssd, dlib, mtcnn, retinaface


def is_face_recognition_available() -> bool:
    """Verifica se as bibliotecas de reconhecimento facial estão disponíveis"""
    available = (DEEPFACE_AVAILABLE and CV2_AVAILABLE and 
                 NUMPY_AVAILABLE and PIL_AVAILABLE)
    
    # Log detalhado se não estiver disponível (apenas para debug)
    if not available:
        missing = []
        if not NUMPY_AVAILABLE:
            missing.append("numpy")
        if not PIL_AVAILABLE:
            missing.append("Pillow")
        if not CV2_AVAILABLE:
            missing.append("opencv-python-headless")
        if not DEEPFACE_AVAILABLE:
            missing.append("deepface")
        
        if missing:
            logging.warning(f"Bibliotecas faltando: {', '.join(missing)}")
    
    return available


def process_uploaded_image(uploaded_file, model_name: str = DEEPFACE_MODEL) -> Optional[Tuple]:
    """
    Processa uma imagem enviada pelo usuário e gera embedding facial usando DeepFace.
    Retorna (embedding facial, imagem PIL) ou None se não encontrar rosto.
    
    Args:
        uploaded_file: Arquivo de imagem enviado
        model_name: Nome do modelo DeepFace a usar (padrão: Facenet)
    
    Returns:
        Tuple com (embedding, imagem) ou None
    """
    if not is_face_recognition_available():
        if st:
            st.error("Bibliotecas de reconhecimento facial não estão instaladas.")
        return None
    
    if not NUMPY_AVAILABLE or not PIL_AVAILABLE or not DEEPFACE_AVAILABLE:
        return None
    
    try:
        # Lê a imagem
        image = Image.open(uploaded_file)
        
        # Converte para RGB se necessário
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Salva temporariamente para DeepFace processar
        temp_path = "temp_face_image.jpg"
        image.save(temp_path, "JPEG")
        
        try:
            # Lista de backends para tentar (do mais rápido ao mais preciso)
            backends_to_try = ['opencv', 'ssd', 'dlib', 'mtcnn', 'retinaface']
            if DEEPFACE_BACKEND in backends_to_try:
                # Move o backend preferido para o início
                backends_to_try.remove(DEEPFACE_BACKEND)
                backends_to_try.insert(0, DEEPFACE_BACKEND)
            
            embedding = None
            last_error = None
            
            # Tenta com enforce_detection=False primeiro (mais tolerante)
            for backend in backends_to_try:
                try:
                    # Primeiro tenta sem enforce_detection (mais tolerante)
                    embedding_obj = DeepFace.represent(
                        img_path=temp_path,
                        model_name=model_name,
                        enforce_detection=False,  # Mais tolerante - não falha se não detectar
                        detector_backend=backend
                    )
                    
                    # Verifica se encontrou algum rosto
                    if embedding_obj:
                        if isinstance(embedding_obj, list) and len(embedding_obj) > 0:
                            # Pega o primeiro rosto (mais confiável)
                            embedding = np.array(embedding_obj[0]['embedding'])
                            logging.info(f"Rosto detectado usando backend: {backend}")
                            break
                        elif isinstance(embedding_obj, dict) and 'embedding' in embedding_obj:
                            embedding = np.array(embedding_obj['embedding'])
                            logging.info(f"Rosto detectado usando backend: {backend}")
                            break
                        
                except Exception as e:
                    last_error = e
                    logging.warning(f"Backend {backend} falhou: {e}")
                    continue
            
            # Se não encontrou com enforce_detection=False, tenta com True (mais rigoroso)
            if embedding is None:
                for backend in backends_to_try[:2]:  # Tenta apenas os 2 primeiros backends
                    try:
                        embedding_obj = DeepFace.represent(
                            img_path=temp_path,
                            model_name=model_name,
                            enforce_detection=True,  # Mais rigoroso
                            detector_backend=backend
                        )
                        
                        if embedding_obj:
                            if isinstance(embedding_obj, list) and len(embedding_obj) > 0:
                                embedding = np.array(embedding_obj[0]['embedding'])
                                logging.info(f"Rosto detectado usando backend: {backend} (enforce_detection=True)")
                                break
                            elif isinstance(embedding_obj, dict) and 'embedding' in embedding_obj:
                                embedding = np.array(embedding_obj['embedding'])
                                logging.info(f"Rosto detectado usando backend: {backend} (enforce_detection=True)")
                                break
                                
                    except Exception as e:
                        last_error = e
                        continue
            
            if embedding is None:
                if st:
                    error_msg = str(last_error) if last_error else "Nenhum rosto detectado"
                    if "Face could not be detected" in error_msg or "No face detected" in error_msg:
                        st.warning("""
                        ⚠️ **Nenhum rosto detectado na imagem.**
                        
                        **Dicas:**
                        - Certifique-se de que há um rosto visível e bem iluminado
                        - Foto frontal, com boa iluminação
                        - Rosto centralizado na imagem
                        - Sem óculos escuros ou objetos cobrindo o rosto
                        - Tente novamente com outra foto
                        """)
                    else:
                        st.warning(f"⚠️ Não foi possível processar a foto. Tente novamente com outra imagem.")
                return None
            
            return embedding, image
            
        finally:
            # Remove arquivo temporário
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
    except Exception as e:
        st.error(f"Erro ao processar imagem: {e}")
        logging.error(f"Erro ao processar imagem: {e}")
        return None


def encoding_to_json(embedding) -> str:
    """Converte um embedding facial numpy para JSON string"""
    return json.dumps(embedding.tolist())


def json_to_encoding(json_str: str):
    """Converte uma string JSON para embedding facial numpy"""
    if not NUMPY_AVAILABLE:
        return None
    return np.array(json.loads(json_str))


def compare_faces(known_embedding, face_embedding_to_check, 
                 threshold: float = 0.4, metric: str = 'cosine') -> Tuple[bool, float]:
    """
    Compara dois embeddings faciais usando DeepFace.
    
    Args:
        known_embedding: Embedding facial conhecido
        face_embedding_to_check: Embedding facial a verificar
        threshold: Threshold para comparação (padrão 0.4 para cosine, menor = mais rigoroso)
        metric: Métrica de distância ('cosine', 'euclidean', 'euclidean_l2')
    
    Returns:
        Tuple (is_match, distance)
    """
    if not is_face_recognition_available():
        return False, float('inf')
    
    try:
        # Calcula a distância usando a métrica especificada
        if metric == 'cosine':
            # Distância cosseno (0 = idêntico, 1 = completamente diferente)
            dot_product = np.dot(known_embedding, face_embedding_to_check)
            norm_a = np.linalg.norm(known_embedding)
            norm_b = np.linalg.norm(face_embedding_to_check)
            distance = 1 - (dot_product / (norm_a * norm_b))
        elif metric == 'euclidean':
            # Distância euclidiana
            distance = np.linalg.norm(known_embedding - face_embedding_to_check)
        elif metric == 'euclidean_l2':
            # Distância euclidiana L2 normalizada
            known_norm = known_embedding / np.linalg.norm(known_embedding)
            check_norm = face_embedding_to_check / np.linalg.norm(face_embedding_to_check)
            distance = np.linalg.norm(known_norm - check_norm)
        else:
            distance = np.linalg.norm(known_embedding - face_embedding_to_check)
        
        # Se a distância for menor que o threshold, são o mesmo rosto
        is_match = distance <= threshold
        
        return is_match, distance
        
    except Exception as e:
        logging.error(f"Erro ao comparar rostos: {e}")
        return False, float('inf')


def find_matching_person(uploaded_file, db_ops, threshold: float = 0.4, 
                        metric: str = 'cosine', model_name: str = DEEPFACE_MODEL) -> Optional[Tuple[dict, float]]:
    """
    Tenta encontrar uma pessoa correspondente comparando o rosto da imagem enviada
    com os embeddings faciais armazenados no banco.
    
    Args:
        uploaded_file: Arquivo de imagem enviado
        db_ops: Instância de SupabaseOperations
        threshold: Threshold para comparação
        metric: Métrica de distância
        model_name: Nome do modelo DeepFace
    
    Returns:
        Tuple (dicionário com dados da pessoa encontrada, distância) ou None
    """
    if not is_face_recognition_available():
        st.error("Bibliotecas de reconhecimento facial não estão instaladas.")
        return None
    
    # Processa a imagem enviada
    result = process_uploaded_image(uploaded_file, model_name)
    if result is None:
        return None
    
    embedding_to_check, _ = result
    
    # Busca todas as pessoas com embedding facial
    try:
        all_people = db_ops.get_people_with_face_encoding()
        
        if not all_people:
            return None
        
        best_match = None
        best_distance = float('inf')
        
        # Compara com cada pessoa
        for person in all_people:
            if not person.get('face_encoding'):
                continue
            
            try:
                known_embedding = json_to_encoding(person['face_encoding'])
                
                is_match, distance = compare_faces(known_embedding, embedding_to_check, threshold, metric)
                
                if is_match and distance < best_distance:
                    best_match = person
                    best_distance = distance
                    
            except Exception as e:
                logging.error(f"Erro ao comparar com pessoa {person.get('id')}: {e}")
                continue
        
        return (best_match, best_distance) if best_match else None
        
    except Exception as e:
        st.error(f"Erro ao buscar pessoas no banco: {e}")
        logging.error(f"Erro ao buscar pessoas: {e}")
        return None


def validate_face_image(image, model_name: str = DEEPFACE_MODEL) -> Tuple[bool, str]:
    """
    Valida se uma imagem é adequada para reconhecimento facial usando DeepFace.
    
    Returns:
        (is_valid, message)
    """
    if not is_face_recognition_available():
        return False, "Bibliotecas de reconhecimento facial não estão instaladas."
    
    try:
        # Salva temporariamente para validação
        temp_path = "temp_validate_image.jpg"
        image.save(temp_path, "JPEG")
        
        try:
            # Lista de backends para tentar
            backends_to_try = ['opencv', 'ssd', 'dlib', 'mtcnn', 'retinaface']
            if DEEPFACE_BACKEND in backends_to_try:
                backends_to_try.remove(DEEPFACE_BACKEND)
                backends_to_try.insert(0, DEEPFACE_BACKEND)
            
            embedding_obj = None
            # Tenta com enforce_detection=False primeiro (mais tolerante)
            for backend in backends_to_try:
                try:
                    embedding_obj = DeepFace.represent(
                        img_path=temp_path,
                        model_name=model_name,
                        enforce_detection=False,  # Mais tolerante
                        detector_backend=backend
                    )
                    if embedding_obj and len(embedding_obj) > 0:
                        break
                except:
                    continue
            
            # Se não encontrou, tenta com enforce_detection=True
            if not embedding_obj or len(embedding_obj) == 0:
                for backend in backends_to_try[:2]:
                    try:
                        embedding_obj = DeepFace.represent(
                            img_path=temp_path,
                            model_name=model_name,
                            enforce_detection=True,
                            detector_backend=backend
                        )
                        if embedding_obj and len(embedding_obj) > 0:
                            break
                    except:
                        continue
            
            if not embedding_obj or len(embedding_obj) == 0:
                return False, "Nenhum rosto detectado na imagem. Tente com melhor iluminação ou foto mais frontal."
            
            # Verifica qualidade da imagem
            width, height = image.size
            if width < 200 or height < 200:
                return False, "Imagem muito pequena. Use uma foto com pelo menos 200x200 pixels."
            
            # Verifica se há múltiplos rostos
            if isinstance(embedding_obj, list) and len(embedding_obj) > 1:
                return False, "Múltiplos rostos detectados. Envie uma foto com apenas um rosto."
            
            return True, "Imagem válida para reconhecimento facial."
            
        except ValueError as e:
            error_msg = str(e)
            if "Face could not be detected" in error_msg or "No face detected" in error_msg:
                return False, "Nenhum rosto detectado na imagem. Tente com melhor iluminação ou foto mais frontal."
            else:
                return False, f"Erro ao validar: {error_msg}"
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
    except Exception as e:
        return False, f"Erro ao validar imagem: {e}"


def draw_face_box(image):
    """
    Desenha uma caixa ao redor do rosto detectado na imagem usando OpenCV.
    Útil para mostrar ao usuário que o rosto foi detectado.
    """
    if not CV2_AVAILABLE or not PIL_AVAILABLE or not NUMPY_AVAILABLE:
        return image
    
    try:
        img_array = np.array(image.convert('RGB'))
        
        # Usa OpenCV para detectar rosto
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        # Desenha retângulo ao redor de cada rosto
        for (x, y, w, h) in faces:
            cv2.rectangle(img_array, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        return Image.fromarray(img_array)
    except Exception as e:
        logging.error(f"Erro ao desenhar caixa: {e}")
        return image


def quick_face_verification(uploaded_file, db_ops, threshold: float = 0.4) -> Tuple[bool, Optional[dict], str]:
    """
    Verificação rápida de rosto no momento do acesso.
    
    Args:
        uploaded_file: Arquivo de imagem enviado
        db_ops: Instância de SupabaseOperations ou SupabasePublicClient
        threshold: Threshold para comparação (padrão 0.4)
    
    Returns:
        Tuple (is_verified, person_data, message)
    """
    if not is_face_recognition_available():
        return False, None, "Bibliotecas de reconhecimento facial não disponíveis."
    
    result = find_matching_person(uploaded_file, db_ops, threshold=threshold)
    
    if result:
        person, distance = result
        return True, person, f"Rosto verificado: {person.get('name', 'N/A')} (distância: {distance:.4f})"
    else:
        return False, None, "Rosto não reconhecido. A pessoa pode não estar cadastrada."
