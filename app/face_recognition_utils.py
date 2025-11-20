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

# Imports opcionais com tratamento de erro
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None
    logging.warning("numpy não está instalado")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    logging.warning("Pillow não está instalado")

try:
    # Tenta importar DeepFace, mas pode falhar se TensorFlow não estiver disponível
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except (ImportError, Exception) as e:
    DEEPFACE_AVAILABLE = False
    DeepFace = None
    # Não loga erro durante importação do módulo para evitar spam
    pass

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
    return (DEEPFACE_AVAILABLE and CV2_AVAILABLE and 
            NUMPY_AVAILABLE and PIL_AVAILABLE)


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
            # Usa DeepFace para gerar embedding
            # enforce_detection=True garante que detecta um rosto
            embedding_obj = DeepFace.represent(
                img_path=temp_path,
                model_name=model_name,
                enforce_detection=True,
                detector_backend=DEEPFACE_BACKEND
            )
            
            # DeepFace retorna uma lista, pegamos o primeiro resultado
            if isinstance(embedding_obj, list):
                embedding = np.array(embedding_obj[0]['embedding'])
            else:
                embedding = np.array(embedding_obj['embedding'])
            
            return embedding, image
            
        except ValueError as e:
            error_msg = str(e)
            if "Face could not be detected" in error_msg or "No face detected" in error_msg:
                st.warning("⚠️ Nenhum rosto detectado na imagem. Por favor, envie uma foto com um rosto visível e bem iluminado.")
            else:
                st.warning(f"⚠️ Erro ao processar rosto: {error_msg}")
            return None
        except Exception as e:
            st.error(f"Erro ao processar imagem com DeepFace: {e}")
            logging.error(f"Erro ao processar imagem: {e}")
            return None
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
            # Tenta detectar rosto
            embedding_obj = DeepFace.represent(
                img_path=temp_path,
                model_name=model_name,
                enforce_detection=True,
                detector_backend=DEEPFACE_BACKEND
            )
            
            # Verifica qualidade da imagem
            height, width = image.size
            if width < 200 or height < 200:
                return False, "Imagem muito pequena. Use uma foto com pelo menos 200x200 pixels."
            
            # Verifica se há múltiplos rostos (DeepFace detecta apenas um por padrão)
            # Mas podemos verificar se há mais de um resultado
            if isinstance(embedding_obj, list) and len(embedding_obj) > 1:
                return False, "Múltiplos rostos detectados. Envie uma foto com apenas um rosto."
            
            return True, "Imagem válida para reconhecimento facial."
            
        except ValueError as e:
            error_msg = str(e)
            if "Face could not be detected" in error_msg or "No face detected" in error_msg:
                return False, "Nenhum rosto detectado na imagem."
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
