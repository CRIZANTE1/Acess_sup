"""
Módulo para processamento e reconhecimento facial usando InsightFace (buffalo_s)
Arquitetura otimizada para Streamlit Cloud - leve, rápido e preciso (ArcFace)
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
# Configura variáveis de ambiente ANTES de importar OpenCV/InsightFace
# Isso evita o erro "libGL.so.1: cannot open shared object file"

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['DISPLAY'] = ':0'
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '0'
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
# Desabilita threading que pode causar problemas
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'

# Tenta configurar OpenCV antes de importar InsightFace
try:
    import cv2
    try:
        cv2.setNumThreads(1)
    except:
        pass
    try:
        cv2.setUseOptimized(False)
    except:
        pass
except ImportError:
    pass
except Exception as e:
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
    # Tenta importar InsightFace - ESSENCIAL para reconhecimento facial
    import insightface
    INSIGHTFACE_AVAILABLE = True
    logging.info("InsightFace importado com sucesso")
except ImportError as e:
    INSIGHTFACE_AVAILABLE = False
    insightface = None
    logging.error(f"❌ ERRO CRÍTICO: InsightFace não pôde ser importado: {e}")
    logging.error("")
    logging.error("🔧 Para instalar, execute:")
    logging.error("   pip install insightface onnxruntime opencv-python-headless numpy Pillow")
    logging.error("")
    logging.error("⚠️ IMPORTANTE: Use opencv-python-headless (não opencv-python) em servidores")
except Exception as e:
    INSIGHTFACE_AVAILABLE = False
    insightface = None
    logging.error(f"ERRO ao importar InsightFace: {e}")

try:
    import cv2
    CV2_AVAILABLE = True
except (ImportError, Exception) as e:
    CV2_AVAILABLE = False
    cv2 = None
    logging.warning(f"opencv-python não está disponível: {e}")

# Configuração do modelo InsightFace
# buffalo_s: Small - Leve/Rápido/Preciso (ideal para Streamlit Cloud)
# buffalo_l: Large - Pesado/Mais Preciso (pode travar no Streamlit Cloud)
INSIGHTFACE_MODEL = os.getenv('INSIGHTFACE_MODEL', 'buffalo_s')

# Variável global para o modelo InsightFace (carregado uma vez)
_insightface_app = None


def _get_insightface_app():
    """
    Obtém ou inicializa o app InsightFace (singleton).
    Carrega o modelo buffalo_s que é otimizado para CPU.
    """
    global _insightface_app
    
    if not INSIGHTFACE_AVAILABLE:
        return None
    
    if _insightface_app is None:
        try:
            # Carrega o modelo buffalo_s (Small - ideal para Streamlit Cloud)
            _insightface_app = insightface.app.FaceAnalysis(
                name=INSIGHTFACE_MODEL,
                providers=['CPUExecutionProvider']  # Força uso de CPU (ONNX Runtime)
            )
            _insightface_app.prepare(ctx_id=-1, det_size=(640, 640))  # ctx_id=-1 = CPU
            logging.info(f"InsightFace modelo '{INSIGHTFACE_MODEL}' carregado com sucesso")
        except Exception as e:
            logging.error(f"Erro ao carregar modelo InsightFace: {e}")
            return None
    
    return _insightface_app


def is_face_recognition_available() -> bool:
    """Verifica se as bibliotecas de reconhecimento facial estão disponíveis"""
    available = (INSIGHTFACE_AVAILABLE and CV2_AVAILABLE and 
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
        if not INSIGHTFACE_AVAILABLE:
            missing.append("insightface")
        
        if missing:
            logging.warning(f"Bibliotecas faltando: {', '.join(missing)}")
    
    return available


def process_uploaded_image(uploaded_file, model_name: str = None) -> Optional[Tuple]:
    """
    Processa uma imagem enviada pelo usuário e gera embedding facial usando InsightFace.
    Retorna (embedding facial, imagem PIL) ou None se não encontrar rosto.
    
    Args:
        uploaded_file: Arquivo de imagem enviado
        model_name: Ignorado (mantido para compatibilidade, usa buffalo_s sempre)
    
    Returns:
        Tuple com (embedding, imagem) ou None
    """
    if not is_face_recognition_available():
        if st:
            st.error("Bibliotecas de reconhecimento facial não estão instaladas.")
        return None
    
    if not NUMPY_AVAILABLE or not PIL_AVAILABLE or not INSIGHTFACE_AVAILABLE:
        return None
    
    try:
        # Lê a imagem
        image = Image.open(uploaded_file)
        
        # Converte para RGB se necessário
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Converte PIL para numpy array (BGR para OpenCV)
        img_array = np.array(image)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Obtém o app InsightFace
        app = _get_insightface_app()
        if app is None:
            if st:
                st.error("Erro ao inicializar modelo de reconhecimento facial.")
            return None
        
        # Detecta e extrai embedding facial
        faces = app.get(img_bgr)
        
        if not faces or len(faces) == 0:
            if st:
                st.warning("""
                ⚠️ **Nenhum rosto detectado na imagem.**
                
                **Dicas:**
                - Certifique-se de que há um rosto visível e bem iluminado
                - Foto frontal, com boa iluminação
                - Rosto centralizado na imagem
                - Sem óculos escuros ou objetos cobrindo o rosto
                - Tente novamente com outra foto
                """)
            return None
        
        # Pega o primeiro rosto (mais confiável se houver múltiplos)
        # Ordena por confiança (bbox.score) - maior = melhor
        faces_sorted = sorted(faces, key=lambda x: x.bbox.score if hasattr(x.bbox, 'score') else 0, reverse=True)
        face = faces_sorted[0]
        
        # Extrai o embedding (vetor de características faciais)
        embedding = face.normed_embedding  # Embedding já normalizado (L2)
        
        return embedding, image
        
    except Exception as e:
        if st:
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
    Compara dois embeddings faciais usando distância cosseno (padrão para ArcFace).
    
    Args:
        known_embedding: Embedding facial conhecido (já normalizado)
        face_embedding_to_check: Embedding facial a verificar (já normalizado)
        threshold: Threshold para comparação (padrão 0.4 para cosine, menor = mais rigoroso)
        metric: Métrica de distância ('cosine' é recomendado para ArcFace)
    
    Returns:
        Tuple (is_match, distance)
    """
    if not is_face_recognition_available():
        return False, float('inf')
    
    try:
        # InsightFace já retorna embeddings normalizados (L2)
        # Para ArcFace, a distância cosseno é a métrica recomendada
        
        if metric == 'cosine':
            # Distância cosseno (0 = idêntico, 1 = completamente diferente)
            # Como os embeddings já estão normalizados, podemos usar produto escalar
            # cosine_similarity = dot_product (já que ||a|| = ||b|| = 1)
            cosine_similarity = np.dot(known_embedding, face_embedding_to_check)
            # Converte similaridade para distância (0 = idêntico, 1 = diferente)
            distance = 1 - cosine_similarity
        elif metric == 'euclidean':
            # Distância euclidiana
            distance = np.linalg.norm(known_embedding - face_embedding_to_check)
        elif metric == 'euclidean_l2':
            # Distância euclidiana L2 normalizada (redundante, mas mantido para compatibilidade)
            known_norm = known_embedding / np.linalg.norm(known_embedding)
            check_norm = face_embedding_to_check / np.linalg.norm(face_embedding_to_check)
            distance = np.linalg.norm(known_norm - check_norm)
        else:
            # Fallback: distância euclidiana
            distance = np.linalg.norm(known_embedding - face_embedding_to_check)
        
        # Se a distância for menor que o threshold, são o mesmo rosto
        is_match = distance <= threshold
        
        return is_match, distance
        
    except Exception as e:
        logging.error(f"Erro ao comparar rostos: {e}")
        return False, float('inf')


def find_matching_person(uploaded_file, db_ops, threshold: float = 0.4, 
                        metric: str = 'cosine', model_name: str = None) -> Optional[Tuple[dict, float]]:
    """
    Tenta encontrar uma pessoa correspondente comparando o rosto da imagem enviada
    com os embeddings faciais armazenados no banco.
    
    Args:
        uploaded_file: Arquivo de imagem enviado
        db_ops: Instância de SupabaseOperations
        threshold: Threshold para comparação (padrão 0.4)
        metric: Métrica de distância ('cosine' recomendado)
        model_name: Ignorado (mantido para compatibilidade)
    
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


def validate_face_image(image, model_name: str = None) -> Tuple[bool, str]:
    """
    Valida se uma imagem é adequada para reconhecimento facial usando InsightFace.
    
    Returns:
        (is_valid, message)
    """
    if not is_face_recognition_available():
        return False, "Bibliotecas de reconhecimento facial não estão instaladas."
    
    try:
        # Converte PIL para numpy array (BGR para OpenCV)
        img_array = np.array(image.convert('RGB'))
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Obtém o app InsightFace
        app = _get_insightface_app()
        if app is None:
            return False, "Erro ao inicializar modelo de reconhecimento facial."
        
        # Detecta rostos
        faces = app.get(img_bgr)
        
        if not faces or len(faces) == 0:
            return False, "Nenhum rosto detectado na imagem. Tente com melhor iluminação ou foto mais frontal."
        
        # Verifica qualidade da imagem
        width, height = image.size
        if width < 200 or height < 200:
            return False, "Imagem muito pequena. Use uma foto com pelo menos 200x200 pixels."
        
        # Verifica se há múltiplos rostos
        if len(faces) > 1:
            return False, "Múltiplos rostos detectados. Envie uma foto com apenas um rosto."
        
        return True, "Imagem válida para reconhecimento facial."
        
    except Exception as e:
        return False, f"Erro ao validar imagem: {e}"


def draw_face_box(image):
    """
    Desenha uma caixa ao redor do rosto detectado na imagem usando InsightFace.
    Útil para mostrar ao usuário que o rosto foi detectado.
    """
    if not CV2_AVAILABLE or not PIL_AVAILABLE or not NUMPY_AVAILABLE or not INSIGHTFACE_AVAILABLE:
        return image
    
    try:
        # Converte PIL para numpy array (BGR para OpenCV)
        img_array = np.array(image.convert('RGB'))
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Obtém o app InsightFace
        app = _get_insightface_app()
        if app is None:
            return image
        
        # Detecta rostos
        faces = app.get(img_bgr)
        
        # Desenha retângulo ao redor de cada rosto
        for face in faces:
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
            cv2.rectangle(img_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Converte de volta para RGB
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)
        
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


def process_video_frame(frame_bgr):
    """
    Processa um frame de vídeo e retorna rostos detectados com embeddings.
    Para uso em stream de vídeo em tempo real.
    
    Args:
        frame_bgr: Frame de vídeo em formato BGR (OpenCV)
    
    Returns:
        Lista de dicionários com informações dos rostos detectados:
        [{'bbox': (x1, y1, x2, y2), 'embedding': np.array, 'confidence': float}, ...]
        ou None se não houver rostos
    """
    if not is_face_recognition_available():
        return None
    
    try:
        # Obtém o app InsightFace
        app = _get_insightface_app()
        if app is None:
            return None
        
        # Detecta rostos no frame
        faces = app.get(frame_bgr)
        
        if not faces or len(faces) == 0:
            return None
        
        # Extrai informações de cada rosto
        results = []
        for face in faces:
            bbox = face.bbox.astype(int)
            embedding = face.normed_embedding
            confidence = float(face.det_score) if hasattr(face, 'det_score') else 1.0
            
            results.append({
                'bbox': (bbox[0], bbox[1], bbox[2], bbox[3]),
                'embedding': embedding,
                'confidence': confidence
            })
        
        return results
        
    except Exception as e:
        logging.error(f"Erro ao processar frame: {e}")
        return None


def find_person_in_frame(frame_bgr, db_ops, threshold: float = 0.4) -> Optional[Tuple[dict, float, tuple]]:
    """
    Processa um frame de vídeo e tenta encontrar uma pessoa cadastrada.
    Para uso em stream de vídeo em tempo real.
    
    Args:
        frame_bgr: Frame de vídeo em formato BGR (OpenCV)
        db_ops: Instância de SupabaseOperations ou SupabasePublicClient
        threshold: Threshold para comparação (padrão 0.4)
    
    Returns:
        Tuple (pessoa, distância, bbox) ou None se não encontrar
        bbox = (x1, y1, x2, y2) coordenadas do rosto no frame
    """
    if not is_face_recognition_available():
        return None
    
    try:
        # Processa o frame e detecta rostos
        detected_faces = process_video_frame(frame_bgr)
        
        if not detected_faces:
            return None
        
        # Busca todas as pessoas cadastradas
        all_people = db_ops.get_people_with_face_encoding()
        
        if not all_people:
            return None
        
        # Para cada rosto detectado, tenta encontrar correspondência
        best_match = None
        best_distance = float('inf')
        best_bbox = None
        
        for detected_face in detected_faces:
            embedding_to_check = detected_face['embedding']
            bbox = detected_face['bbox']
            
            # Compara com cada pessoa cadastrada
            for person in all_people:
                if not person.get('face_encoding'):
                    continue
                
                try:
                    known_embedding = json_to_encoding(person['face_encoding'])
                    is_match, distance = compare_faces(known_embedding, embedding_to_check, threshold)
                    
                    if is_match and distance < best_distance:
                        best_match = person
                        best_distance = distance
                        best_bbox = bbox
                        
                except Exception as e:
                    logging.error(f"Erro ao comparar com pessoa {person.get('id')}: {e}")
                    continue
        
        return (best_match, best_distance, best_bbox) if best_match else None
        
    except Exception as e:
        logging.error(f"Erro ao processar frame para reconhecimento: {e}")
        return None


def draw_face_boxes_on_frame(frame_bgr, faces_info, show_names=False):
    """
    Desenha caixas ao redor dos rostos detectados em um frame de vídeo.
    
    Args:
        frame_bgr: Frame de vídeo em formato BGR (OpenCV)
        faces_info: Lista de dicionários com informações dos rostos
                   [{'bbox': (x1,y1,x2,y2), 'name': str, 'confidence': float}, ...]
        show_names: Se True, mostra o nome da pessoa acima da caixa
    
    Returns:
        Frame com caixas desenhadas
    """
    if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
        return frame_bgr
    
    try:
        frame_copy = frame_bgr.copy()
        
        for face_info in faces_info:
            bbox = face_info.get('bbox')
            if not bbox:
                continue
            
            x1, y1, x2, y2 = bbox
            name = face_info.get('name', 'Desconhecido')
            confidence = face_info.get('confidence', 0.0)
            
            # Define cor da caixa (verde se reconhecido, vermelho se não)
            color = (0, 255, 0) if name != 'Desconhecido' else (0, 0, 255)
            
            # Desenha retângulo
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 2)
            
            # Desenha nome e confiança se solicitado
            if show_names:
                text = f"{name} ({confidence:.2f})"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2
                
                # Calcula tamanho do texto
                (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)
                
                # Desenha fundo do texto
                cv2.rectangle(frame_copy, (x1, y1 - text_height - 10), (x1 + text_width, y1), color, -1)
                
                # Desenha texto
                cv2.putText(frame_copy, text, (x1, y1 - 5), font, font_scale, (255, 255, 255), thickness)
        
        return frame_copy
        
    except Exception as e:
        logging.error(f"Erro ao desenhar caixas: {e}")
        return frame_bgr
