import json
import chromadb
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from flask import Blueprint, request, jsonify
from PIL import Image
import io
import numpy as np
import cv2
import os
import easyocr
import logging
from dotenv import load_dotenv


# Giới hạn bộ nhớ và tắt log
os.environ['FLAGS_allocator_strategy'] = 'auto_growth'
logging.getLogger('ppocr').setLevel(logging.ERROR)

# ================================
# 🔑 CẤU HÌNH GEMINI API
# ================================

GEMINI_API_KEY = os.getenv("API_KEY")
GEMINI_MODEL_NAME = "gemini-2.5-flash"  
genai.configure(api_key=GEMINI_API_KEY)

# ================================
# ⚙️ 1. Khởi tạo ChromaDB + Embedding Model
# ================================
model = SentenceTransformer("intfloat/multilingual-e5-base")
chroma_client = chromadb.Client(chromadb.config.Settings(persist_directory="./chroma_db"))
collection = chroma_client.get_or_create_collection("restaurants")

# ================================
# 🚀 SINGLETON EASYOCR
# ================================
class OCRProcessor:
    """Singleton Pattern để khởi tạo EasyOCR chỉ 1 lần"""
    _instance = None
    _reader_en = None
    _reader_vi = None
    _initialized = False
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if not OCRProcessor._initialized:
            print("🔧 Đang khởi tạo EasyOCR engines...")
            try:
                print("   → Loading English OCR...")
                self._reader_en = easyocr.Reader(['en'], gpu=False, verbose=False)
                
                print("   → Loading Vietnamese OCR...")
                self._reader_vi = easyocr.Reader(['vi'], gpu=False, verbose=False)
                
                OCRProcessor._initialized = True
                print("✅ EasyOCR engines sẵn sàng!")
            except Exception as e:
                print(f"❌ Lỗi khởi tạo EasyOCR: {e}")
                raise
    
    def get_ocr(self, lang='en'):
        """Lấy OCR engine theo ngôn ngữ"""
        return self._reader_en if lang == 'en' else self._reader_vi

# ================================
# 🖼️ TIỀN XỬ LÝ ẢNH
# ================================
def preprocess_image(image: Image.Image) -> np.ndarray:
    """Tiền xử lý ảnh cho EasyOCR"""
    try:
        img_np = np.array(image)
        
        # Resize nếu ảnh quá lớn
        height, width = img_np.shape[:2]
        max_size = 1920
        if max(height, width) > max_size:
            scale = max_size / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img_np = cv2.resize(img_np, (new_width, new_height))
            print(f"   → Resize: {width}x{height} → {new_width}x{new_height}")
        
        return img_np
    except Exception as e:
        print(f"⚠️ Lỗi preprocessing: {e}")
        return np.array(image)

# ================================
# 📝 TRÍCH XUẤT TEXT TỪ EASYOCR
# ================================
def extract_text_from_ocr_result(result) -> str:
    """
    Trích xuất text từ kết quả EasyOCR
    Format: [([bbox], text, confidence), ...]
    """
    print("=" * 60)
    print("🔍 PHÂN TÍCH KẾT QUẢ EASYOCR")
    
    if not result:
        print("❌ Result rỗng!")
        return ""
    
    print(f"✓ Tìm thấy {len(result)} detections")
    
    text_data = []
    
    for idx, detection in enumerate(result):
        try:
            bbox = detection[0]
            text = detection[1]
            confidence = detection[2]
            
            # Tính tọa độ trung tâm
            center_y = (bbox[0][1] + bbox[2][1]) / 2
            center_x = (bbox[0][0] + bbox[2][0]) / 2
            
            if confidence > 0.3 and len(text.strip()) > 0:
                text_data.append({
                    'text': text.strip(),
                    'confidence': confidence,
                    'center_y': center_y,
                    'center_x': center_x
                })
                print(f"  [{idx}] '{text[:30]}...' | Conf: {confidence:.2f}")
        except Exception as e:
            print(f"  [{idx}] ⚠️ Lỗi: {e}")
            continue
    
    if not text_data:
        print("❌ Không có text nào đạt ngưỡng confidence > 0.3")
        return ""
    
    # Sắp xếp: trên xuống dưới, trái sang phải
    text_data.sort(key=lambda x: (x['center_y'] // 20, x['center_x']))
    
    # Ghép text với xuống dòng thông minh
    lines = []
    current_line = []
    current_y = text_data[0]['center_y']
    
    for item in text_data:
        y = item['center_y']
        text = item['text']
        
        if abs(y - current_y) > 20:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [text]
            current_y = y
        else:
            current_line.append(text)
    
    if current_line:
        lines.append(" ".join(current_line))
    
    final_text = "\n".join(lines)
    
    print(f"\n✅ Tổng cộng: {len(text_data)} texts | {len(lines)} dòng")
    print(f"📝 Preview: {final_text[:200]}...")
    print("=" * 60)
    
    return final_text

# ================================
# 🖼️ XỬ LÝ OCR & DỊCH MENU
# ================================
def process_menu_image(image_data: bytes, target_language: str = 'vi') -> dict:
    """Xử lý ảnh menu: EasyOCR + Gemini Dịch"""
    try:
        print("\n" + "=" * 70)
        print("🚀 BẮT ĐẦU XỬ LÝ ẢNH MENU (EASYOCR)")
        print("=" * 70)
        
        # 1. Load ảnh
        print("📷 [1/5] Đang load ảnh...")
        image = Image.open(io.BytesIO(image_data))
        print(f"   ✓ Size: {image.size} | Mode: {image.mode}")
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        direction = 'EN→VI' if target_language == 'vi' else 'VI→EN'
        print(f"🌐 [2/5] Hướng dịch: {direction}")
        
        # 2. Tiền xử lý
        print("🔧 [3/5] Tiền xử lý ảnh...")
        processed_image = preprocess_image(image)
        
        # 3. Lấy OCR engine
        print("🔍 [4/5] Khởi tạo OCR...")
        ocr_lang = 'en' if target_language == 'vi' else 'vi'
        ocr_processor = OCRProcessor.get_instance()
        reader = ocr_processor.get_ocr(ocr_lang)
        print(f"   ✓ Sử dụng OCR: {ocr_lang}")
        
        # 4. Chạy OCR
        print("📖 [5/5] Đang OCR ảnh...")
        result = reader.readtext(processed_image)
        
        # 5. Trích xuất text
        extracted_text = extract_text_from_ocr_result(result)
        
        if not extracted_text or len(extracted_text.strip()) < 3:
            print("\n⚠️ Kết quả quá ngắn, thử lại với ảnh gốc...")
            img_original = np.array(image)
            result2 = reader.readtext(img_original)
            extracted_text = extract_text_from_ocr_result(result2)
            
            if not extracted_text or len(extracted_text.strip()) < 3:
                return {
                    'success': False,
                    'error': 'Không đọc được text từ ảnh. Vui lòng thử:\n'
                             '• Ảnh chụp thẳng, không bị nghiêng\n'
                             '• Ánh sáng đủ, không bị tối\n'
                             '• Text rõ ràng, không bị mờ\n'
                             '• Kích thước ảnh > 800x600px'
                }
        
        print(f"\n✅ OCR THÀNH CÔNG!")
        print(f"   Chiều dài: {len(extracted_text)} ký tự")
        
        # 6. Dịch bằng Gemini với XỬ LÝ AN TOÀN
        print("\n🤖 Đang dịch với Gemini...")
        
        # CẮT TEXT NẾU QUÁ DÀI (tránh lỗi safety)
        max_length = 2000
        if len(extracted_text) > max_length:
            print(f"   ⚠️ Text quá dài ({len(extracted_text)} chars), cắt xuống {max_length}")
            extracted_text = extracted_text[:max_length] + "..."
        
        if target_language == 'vi':
            prompt = f"""Dịch menu từ tiếng Anh sang tiếng Việt. CHỈ trả về bản dịch.

TEXT:
{extracted_text}"""
        else:
            prompt = f"""Translate to English. ONLY return translation.

TEXT:
{extracted_text}"""
        
        # THỬ CÁC MODEL VỚI XỬ LÝ SAFETY
        models_to_try = [
            'gemini-2.5-flash',
            
            'gemini-2.5-pro'
        ]
        
        translated_text = None
        last_error = None
        
        for model_name in models_to_try:
            try:
                print(f"   → Thử model: {model_name}")
                gm = genai.GenerativeModel(model_name)
                
                # Tăng safety settings
                safety_settings = {
                    'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                    'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                    'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                    'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
                }
                
                response = gm.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=2048,
                    ),
                    safety_settings=safety_settings
                )
                
                # XỬ LÝ RESPONSE AN TOÀN
                if response.candidates:
                    candidate = response.candidates[0]
                    
                    # Kiểm tra finish_reason
                    finish_reason = candidate.finish_reason
                    print(f"   → Finish reason: {finish_reason}")
                    
                    # finish_reason có thể là int hoặc enum
                    # 1 = STOP (thành công), 2 = SAFETY, 3 = RECITATION, 4 = OTHER
                    if finish_reason in [1, 'STOP']:  # STOP (thành công)
                        if candidate.content and candidate.content.parts:
                            translated_text = candidate.content.parts[0].text.strip()
                            print(f"   ✓ Thành công với {model_name}")
                            break
                        else:
                            print(f"   ✗ {model_name}: No content parts")
                            continue
                    elif finish_reason in [2, 'SAFETY']:  # SAFETY
                        print(f"   ✗ {model_name}: Blocked by safety filter")
                        # Thử prompt đơn giản hơn
                        if "YÊU CẦU:" in prompt or "REQUIREMENTS:" in prompt:
                            print(f"   → Thử prompt đơn giản hơn...")
                            simple_prompt = f"Translate to {'Vietnamese' if target_language == 'vi' else 'English'}:\n\n{extracted_text}"
                            try:
                                response2 = gm.generate_content(
                                    simple_prompt,
                                    generation_config=genai.GenerationConfig(temperature=0.3, max_output_tokens=2048),
                                    safety_settings=safety_settings
                                )
                                if response2.candidates and response2.candidates[0].finish_reason in [1, 'STOP']:
                                    if response2.candidates[0].content and response2.candidates[0].content.parts:
                                        translated_text = response2.candidates[0].content.parts[0].text.strip()
                                        print(f"   ✓ Thành công với prompt đơn giản")
                                        break
                            except:
                                pass
                        continue
                    elif finish_reason in [3, 'RECITATION']:  # RECITATION
                        print(f"   ✗ {model_name}: Blocked by recitation filter")
                        continue
                    else:
                        print(f"   ✗ {model_name}: finish_reason={finish_reason}")
                        continue
                else:
                    print(f"   ✗ {model_name}: No candidates")
                    continue
                    
            except Exception as e:
                last_error = str(e)
                print(f"   ✗ {model_name} failed: {str(e)[:100]}")
                if '429' in str(e):
                    continue
                elif 'finish_reason' in str(e):
                    continue
                else:
                    continue
        
        if not translated_text:
            # FALLBACK: Chỉ trả về text gốc, KHÔNG có gợi ý dài dòng
            print(f"\n⚠️ Không thể dịch được. Trả về text gốc.")
            return {
                'success': True,
                'original_text': extracted_text,
                'translated_text': f"⚠️ Không thể dịch tự động. Đây là text đã OCR:\n\n{extracted_text}",
                'stats': {
                    'original_length': len(extracted_text),
                    'translated_length': len(extracted_text),
                    'direction': direction,
                    'warning': 'Translation failed - returned OCR text'
                }
            }
        
        # Loại markdown
        if '```' in translated_text:
            translated_text = translated_text.replace('```json', '').replace('```', '').strip()
        
        print("✅ HOÀN TẤT!")
        print("=" * 70 + "\n")
        
        return {
            'success': True,
            'original_text': extracted_text,
            'translated_text': translated_text,
            'stats': {
                'original_length': len(extracted_text),
                'translated_length': len(translated_text),
                'direction': direction
            }
        }
        
    except Exception as e:
        print(f"\n❌ LỖI: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Lỗi xử lý: {str(e)}'
        }

# ================================
# 📂 2. Nạp dữ liệu JSON vào ChromaDB
# ================================
count = len(collection.get()["ids"])
if count == 0:
    print("🆕 Database trống – bắt đầu nạp dữ liệu JSON...")
    with open("foods.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    docs, metas, ids = [], [], []
    for i, item in enumerate(data):
    # Tạo text embedding
        text = f"""
        Tên món: {item['name']}
        Xuất xứ: {item['origin']}
        Loại: {item['category']}
        Giá: {item['price_range']}
        Nguyên liệu: {', '.join(item['ingredients'])}
        Chất gây dị ứng: {', '.join(item.get('allergens', []))}
        Calo: {item['calos']}
        Khẩu phần: {item['serving_size']}
        Cách chế biến: {item['cooking_method']}
        Hương vị: {item['flavor_profile']}
        Lịch sử: {item['history']}
        Ý nghĩa văn hóa: {item['cultural_significance']}
        Vị: {item['taste']}
        Gợi ý: {' | '.join(item['suggestions'])}
        """
        docs.append(text)
    
    # Tạo metadata
        metas.append({
            "name": item["name"],
            "origin": item["origin"],
            "category": item["category"],
            "price_range": item["price_range"],
            "ingredients": ', '.join(item["ingredients"]),
            "allergens": ', '.join(item.get("allergens", [])),
            "calos": item["calos"],
            "serving_size": item["serving_size"],
            "cooking_method": item["cooking_method"],
            "flavor_profile": item["flavor_profile"],
            "taste": item["taste"],
            "vegetarian": str(item["diet_type"].get("vegetarian", False)),
            "low_carb": str(item["diet_type"].get("low_carb", False)),
            "history": item["history"],
            "cultural_significance": item["cultural_significance"],
            "suggestions": ' | '.join(item["suggestions"])
        })
        ids.append(str(i))

    embeddings = model.encode(docs).tolist()
    collection.add(documents=docs, embeddings=embeddings, ids=ids, metadatas=metas)
    print(f"✅ Đã nạp {len(docs)} món ăn vào database.")
else:
    print(f"✅ Database đã có sẵn {count} mục.")

# ================================
# 🧠 3. Conversation Manager
# ================================
class ConversationManager:
    def __init__(self, max_turns = 3):
        self.conversation_history = []
        self.max_turns = max_turns
    
    def add_to_history(self, role: str, message: str):
        self.conversation_history.append({"role": role, "content": message})
        if len(self.conversation_history) > self.max_turns * 2:
            self.conversation_history = self.conversation_history[-(self.max_turns*2):]
    
    def get_history_text(self):
        if not self.conversation_history:
            return "Chưa có lịch sử hội thoại."
        
        history_text = ""
        for msg in self.conversation_history[-6:]:
            role = "User" if msg["role"] == "user" else "Deadline"
            history_text += f"{role}: {msg['content']}\n"
        return history_text

conv_manager = ConversationManager()

# ================================
# 🤖 Hàm gọi Gemini
# ================================
def generate_answer_with_gemini(prompt: str, response_language: str = 'vi') -> str:
    """
    Gọi Gemini và đảm bảo trả lời theo ngôn ngữ chỉ định
    response_language: 'vi' hoặc 'en'
    """
    try:
        print(f"🟢 Gemini called with response_language='{response_language}'")  # ← THÊM DÒNG NÀY
        # Thêm yêu cầu ngôn ngữ vào prompt
        if response_language == 'en':
            language_instruction = "\n\nIMPORTANT: You MUST respond in ENGLISH only, regardless of the user's language."
            prompt = prompt + language_instruction
        else:
            language_instruction = "\n\nQUAN TRỌNG: Bạn PHẢI trả lời bằng TIẾNG VIỆT, bất kể người dùng dùng ngôn ngữ gì."
            prompt = prompt + language_instruction
        
        gm = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = gm.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print("⚠️ Lỗi khi gọi Gemini:", e)
        raise

# ================================
# 🎯 HYBRID RAG
# ================================
def smart_rag_chat(question: str, response_language: str = 'vi') -> str:
    conv_manager.add_to_history("user", question)
    
    medical_keywords = [
        "ung thư", "bệnh", "suy thận", "tiểu đường", "cao huyết áp",
        "dị ứng", "bệnh viện", "thuốc", "điều trị", "chữa", "khỏi",
        "triệu chứng", "đau", "viêm", "nhiễm trùng", "sốt",
        "cancer", "disease", "kidney", "diabetes", "hypertension",
        "allergy", "hospital", "medicine", "treatment", "cure", "heal",
        "symptom", "pain", "inflammation", "infection", "fever"
    ]
    
    is_medical_query = any(keyword in question.lower() for keyword in medical_keywords)

    query_emb = model.encode([question]).tolist()[0]
    results = collection.query(
        query_embeddings=[query_emb], 
        n_results=5,
        include=["documents", "metadatas", "distances"]
    )
    
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    
    relevant_docs = []
    relevant_metas = []
    relevant_distances = []
    
    for doc, meta, dist in zip(documents, metadatas, distances):
        relevant_docs.append(doc)
        relevant_metas.append(meta)
        relevant_distances.append(dist)
    
    best_distance = relevant_distances[0] if relevant_distances else 999
    
    if best_distance < 0.8:
        threshold = 1.2
    elif best_distance < 1.5:
        threshold = 1.5
    else:
        threshold = 999
    
    filtered_docs = []
    filtered_metas = []
    for doc, meta, dist in zip(relevant_docs, relevant_metas, relevant_distances):
        if dist < threshold:
            filtered_docs.append(doc)
            filtered_metas.append(meta)
    
    if len(filtered_docs) < 3 and len(relevant_docs) >= 3:
        filtered_docs = relevant_docs[:3]
        filtered_metas = relevant_metas[:3]
    elif not filtered_docs and relevant_docs:
        filtered_docs = relevant_docs[:1]
        filtered_metas = relevant_metas[:1]
    
    relevant_docs = filtered_docs
    relevant_metas = filtered_metas
    
    database_info = ""
    if relevant_docs:
        database_info = "📚 THÔNG TIN TỪ DATABASE:\n"
        for i, doc in enumerate(relevant_docs[:3], 1):
            lines = doc.strip().split('\n')
            dish_name = ""
            
            for line in lines:
                if "Tên món:" in line:
                    dish_name = line.split(":", 1)[1].strip()
            
            database_info += f"\n--- Món {i}: {dish_name} ---\n"
            database_info += doc + "\n"
    else:
        database_info = (
            "📚 DATABASE: Hiện chưa có thông tin về món ăn này trong cơ sở dữ liệu."
        )
    
    history_text = conv_manager.get_history_text()

    if is_medical_query:
        # Prompt y tế - tùy theo ngôn ngữ trả lời
        if response_language == 'en':
            prompt = f"""You are Deadline - Ho Chi Minh City food expert.

⚠️ WARNING: This is a health/medical question.

CONVERSATION HISTORY (for reference):
{history_text}

{database_info}

QUESTION: {question}

MANDATORY RULES:
1. DO NOT give medical/nutritional treatment advice
2. DO NOT suggest dishes as "good for disease X"
3. ONLY respond in ENGLISH:
   "⚠️ I'm just a food chatbot, I cannot provide health advice.
   
   For [disease name] condition, you SHOULD:
   - Consult a doctor/nutrition specialist
   - Follow prescribed diet plan
   
   If you want to find dishes by taste preference, I can help! 🍽️"

ABSOLUTELY do not say "dish X is good for disease Y"."""
        else:
            prompt = f"""Bạn là Deadline - chuyên gia ẩm thực TP.HCM.

⚠️ CẢNH BÁO: Câu hỏi liên quan đến sức khỏe/bệnh tật.

LỊCH SỬ (chỉ tham khảo):
{history_text}

{database_info}

CÂU HỎI: {question}

QUY TẮC BẮT BUỘC:
1. KHÔNG đưa ra lời khuyên y tế/dinh dưỡng điều trị
2. KHÔNG gợi ý món ăn "tốt cho bệnh X"
3. CHỈ trả lời bằng TIẾNG VIỆT: 
   "⚠️ Mình chỉ là chatbot ẩm thực, không thể tư vấn sức khỏe.
   
   Với tình trạng [tên bệnh], bạn NÊN:
   - Hỏi ý kiến bác sĩ/chuyên gia dinh dưỡng
   - Tham khảo chế độ ăn được kê đơn
   
   Nếu muốn tìm món ăn theo khẩu vị, mình có thể gợi ý nhé! 🍽️"

TUYỆT ĐỐI không nói "món X tốt cho bệnh Y"."""
    else:
        # Prompt bình thường - tùy theo ngôn ngữ trả lời
        if response_language == 'en':
            prompt = f"""You are Deadline - a smart, friendly Ho Chi Minh City food expert.

CONVERSATION HISTORY (for context):
{history_text}

{database_info}

CURRENT QUESTION: {question}

RESPONSE RULES:
1. PRIORITIZE answering the CURRENT question, not influenced by history
2. If asking about a new dish → reset context, introduce the new dish
3. If asking for more details → use database info for that dish
4. Respond in 4-6 sentences, concise
5. End with 1-2 suggestions from the suggestions field
6. You MUST respond in ENGLISH regardless of user's language

EXAMPLE:
- User asks "What is Bún bò?" → Introduce Bún bò
- User then asks "What about Phở?" → RESET, introduce Phở (DON'T mention Bún bò)
- User asks "How much is that?" → Based on most recent question

DO NOT fabricate information not in database."""
        else:
            prompt = f"""Bạn là Deadline - chuyên gia ẩm thực TP.HCM thông minh, thân thiện.

LỊCH SỬ (tham khảo ngữ cảnh):
{history_text}

{database_info}

CÂU HỎI HIỆN TẠI: {question}

QUY TẮC TRẢ LỜI:
1. ƯU TIÊN trả lời câu hỏi HIỆN TẠI, không bị ảnh hưởng bởi lịch sử
2. Nếu hỏi món mới → reset ngữ cảnh, giới thiệu món mới
3. Nếu hỏi thêm chi tiết → dùng thông tin từ database của món đó
4. Trả lời 4-6 câu, ngắn gọn
5. Kết thúc bằng 1-2 gợi ý từ trường suggestions
6. Bạn PHẢI trả lời bằng TIẾNG VIỆT bất kể người dùng dùng ngôn ngữ gì

VÍ DỤ:
- User hỏi "Bún bò là gì?" → Giới thiệu bún bò
- User hỏi tiếp "Phở thì sao?" → RESET, giới thiệu phở (KHÔNG nhắc bún bò)
- User hỏi "Món đó giá bao nhiêu?" → Dựa vào câu hỏi gần nhất

KHÔNG bịa đặt thông tin không có trong database."""

    
    
# - Trả lời NGẮN GỌN (4-6 câu), tự nhiên như Gen Z
# - Ưu tiên thông tin từ database (tên món, xuất xứ, giá, calo, nguyên liệu, hương vị)
# - Nếu hỏi về chế độ ăn (chay/low-carb), dựa vào trường diet_type
# - Nếu hỏi về dị ứng, nhắc đến allergens
# - Nếu hỏi lịch sử/văn hóa, trích dẫn history và cultural_significance
# - Kết thúc bằng 1-2 gợi ý từ trường suggestions
# - Không bịa đặt thông tin không có trong database"""
    
    try:
        content = generate_answer_with_gemini(prompt, response_language)
    except Exception as e:
        print("⚠️ Gemini lỗi:", e)
        if relevant_docs:
            content = f"🍽️ Mình tìm thấy {relevant_metas[0]['name']}!\n\n"
            content += f"📍 Xuất xứ: {relevant_metas[0]['origin']}\n"
            content += f"💵 Giá: {relevant_metas[0]['price_range']}\n"
            content += f"🎯 Vị: {relevant_metas[0]['taste']}"
        else:
            content = "😢 Hiện hệ thống chưa có dữ liệu về món này."
    
    conv_manager.add_to_history("assistant", content)
    return str(content)

# ================================
# 🌐 Flask Blueprint
# ================================
chatbox_bp = Blueprint('chatbox', __name__)

@chatbox_bp.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()
    response_language = data.get('response_language', 'vi')
    
    if not question:
        return jsonify({"answer": "⚠ Vui lòng nhập câu hỏi hợp lệ."}), 200
    
    print(f"🔵 Backend received: question='{question}', response_language='{response_language}'")  # ← THÊM DÒNG NÀY

    answer = smart_rag_chat(question,response_language)
    return jsonify({"answer": answer}), 200

@chatbox_bp.route("/translate-menu", methods=["POST"])
def translate_menu():
    """Endpoint dịch menu từ ảnh"""
    try:
        if 'image' not in request.files:
            return jsonify({
                'success': False, 
                'answer': '⚠️ Không có file ảnh được upload'
            }), 400
        
        file = request.files['image']
        target_language = request.form.get('targetLanguage', 'vi')
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'answer': '⚠️ Không có file được chọn'
            }), 400

        image_bytes = file.read()
        result = process_menu_image(image_bytes, target_language)
        
        if result['success']:
            # ✅ CHỈ HIỂN THỊ BẢN DỊCH, KHÔNG CẦN TEXT GỐC
            answer = f"✨ **Bản dịch menu:**\n\n{result['translated_text']}"
            
            return jsonify({
                'success': True,
                'answer': answer,
                'original_text': result['original_text'],
                'translated_text': result['translated_text'],
                'stats': result.get('stats', {})
            }), 200
        else:
            return jsonify({
                'success': False,
                'answer': f"❌ {result['error']}"
            }), 400
        
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'answer': f'❌ Có lỗi xảy ra: {str(e)}'
        }), 500

print("""
🍕 CHÀO MỪNG ĐẾN VỚI DEADLINE - HYBRID VERSION! 🍜

✨ Kết hợp tốt nhất:
• ChromaDB + Embedding: Tìm kiếm chính xác
• Gemini 1.5 Flash: Trả lời tự nhiên
• EasyOCR: Đọc menu từ ảnh

📡 Endpoints: POST /ask, POST /translate-menu
""")