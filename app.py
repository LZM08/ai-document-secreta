import os
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from pdf2image import convert_from_path
import numpy as np
import docx
from paddleocr import PaddleOCR
from PIL import Image
import requests
import json
import traceback
import time

# .env 파일 로드
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')  # 세션을 위한 시크릿 키

# PaddleOCR 초기화
ocr = PaddleOCR(
    use_angle_cls=True,          # 텍스트 방향 감지
    lang='korean',               # 한국어 모델
    use_gpu=False,               # GPU 사용 여부
    show_log=False,              # 로그 출력 제한
    ocr_version='PP-OCRv4',      # 최신 버전 사용
    det_db_thresh=0.3,           # 텍스트 검출 임계값
    det_db_box_thresh=0.5,       # 텍스트 박스 검출 임계값
    det_db_unclip_ratio=1.6,     # 텍스트 영역 확장 비율
    rec_batch_num=6,             # 인식 배치 크기
    max_text_length=800,         # 최대 텍스트 길이
    rec_algorithm='SVTR_LCNet',  # 텍스트 인식 알고리즘
    drop_score=0.5,              # 낮은 신뢰도 결과 제거
    rec_image_shape='3, 48, 320' # 이미지 형태
)

# DeepSeek API 설정
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://free.yunwu.ai/v1/chat/completions"

# 파일 업로드 설정
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image_with_ocr(image):
    try:
        # 이미지를 numpy 배열로 변환
        img_array = np.array(image)
        
        # OCR 실행
        result = ocr.ocr(img_array, cls=True)
        print("OCR 실행 완료")
        
        if not result or not result[0]:
            print("OCR 결과가 없습니다.")
            return None
        
        # 결과 정렬 (위에서 아래로, 왼쪽에서 오른쪽으로)
        sorted_boxes = sorted(result[0], key=lambda x: (x[0][0][1], x[0][0][0]))
        print(f"인식된 텍스트 박스 수: {len(sorted_boxes)}")
        
        # 줄 단위로 텍스트 그룹화
        current_line_y = None
        line_threshold = 10  # 같은 줄로 인식할 y좌표 차이 임계값
        lines = []
        current_line = []
        
        for box in sorted_boxes:
            if not box or len(box) < 2 or not isinstance(box[1], tuple):
                continue
                
            text = box[1][0].strip()
            confidence = box[1][1]
            box_y = sum(point[1] for point in box[0]) / 4  # y 좌표 평균
            
            # 신뢰도가 너무 낮은 결과는 제외
            if confidence < 0.5:
                continue
            
            if not text:
                continue
                
            if current_line_y is None:
                current_line_y = box_y
                current_line.append(text)
            elif abs(box_y - current_line_y) <= line_threshold:
                current_line.append(text)
            else:
                lines.append(' '.join(current_line))
                current_line = [text]
                current_line_y = box_y
        
        # 마지막 줄 처리
        if current_line:
            lines.append(' '.join(current_line))
        
        if not lines:
            print("추출된 텍스트가 없습니다.")
            return None
        
        # 줄 단위로 결합
        text = '\n'.join(line for line in lines if line.strip())
        print(f"추출된 텍스트 줄 수: {len(lines)}")
        return text
        
    except Exception as e:
        print(f"OCR 처리 중 오류 발생: {str(e)}")
        traceback.print_exc()
        return None

def extract_text_from_file(file_path):
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        print(f"파일 확장자: {file_extension}")
        
        if file_extension == '.pdf':
            try:
                print("PDF를 이미지로 변환 중...")
                images = convert_from_path(file_path)
                print(f"변환된 이미지 수: {len(images)}")
                
                text = ''
                for i, image in enumerate(images, 1):
                    print(f"페이지 {i}/{len(images)} 처리 중")
                    page_text = process_image_with_ocr(image)
                    if page_text:
                        text += f"\n=== 페이지 {i} ===\n" + page_text + '\n'
                
                if not text.strip():
                    print("PDF에서 텍스트를 추출할 수 없습니다.")
                    return None
                    
                return text
                
            except Exception as e:
                print(f"PDF 처리 중 오류 발생: {str(e)}")
                traceback.print_exc()
                return None
        
        elif file_extension in ['.docx', '.doc']:
            try:
                print("DOCX 파일 처리 중...")
                doc = docx.Document(file_path)
                text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                if not text.strip():
                    print("DOCX 파일에서 텍스트를 추출할 수 없습니다.")
                    return None
                return text
            except Exception as e:
                print(f"DOCX 처리 중 오류 발생: {str(e)}")
                traceback.print_exc()
                return None
        
        elif file_extension in ['.png', '.jpg', '.jpeg']:
            try:
                print("이미지 파일 처리 중...")
                image = Image.open(file_path)
                text = process_image_with_ocr(image)
                if not text:
                    print("이미지에서 텍스트를 추출할 수 없습니다.")
                    return None
                return text
            except Exception as e:
                print(f"이미지 처리 중 오류 발생: {str(e)}")
                traceback.print_exc()
                return None
        
        else:
            print(f"지원되지 않는 파일 형식: {file_extension}")
            return None
            
    except Exception as e:
        print(f"파일 처리 중 오류 발생: {str(e)}")
        traceback.print_exc()
        return None



def analyze_with_deepseek(text, conversation_history=None, max_retries=3, timeout=30):
    if not text:
        print("분석할 텍스트가 없습니다.")
        return "텍스트가 비어있습니다.", None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    if conversation_history is None:
        messages = [
            {"role": "system", "content": "당신은 문서 분석 전문 AI 어시스턴트입니다. 제공된 텍스트를 상세히 분석해주세요."},
            {"role": "user", "content": f"다음 문서를 분석해주세요:\n\n{text}"}
        ]
    else:
        messages = conversation_history + [
            {"role": "user", "content": text}
        ]

    data = {
        "model": "deepseek-r1",
        "messages": messages
    }

    for attempt in range(max_retries):
        try:
            print(f"DeepSeek API 요청 시도 {attempt + 1}/{max_retries}")
            response = requests.post(
                DEEPSEEK_API_URL, 
                headers=headers, 
                json=data,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'], messages + [{"role": "assistant", "content": result['choices'][0]['message']['content']}]
            
        except requests.exceptions.Timeout:
            print(f"시도 {attempt + 1}: 타임아웃 발생")
            if attempt == max_retries - 1:
                return "API 응답 시간 초과. 잠시 후 다시 시도해주세요.", None
                
        except requests.exceptions.RequestException as e:
            print(f"시도 {attempt + 1}: 요청 실패 - {str(e)}")
            if attempt == max_retries - 1:
                return f"API 요청 실패: {str(e)}", None
                
        except Exception as e:
            print(f"시도 {attempt + 1}: 예상치 못한 오류 - {str(e)}")
            traceback.print_exc()
            if attempt == max_retries - 1:
                return f"오류 발생: {str(e)}", None
        
        # 재시도 전 대기
        if attempt < max_retries - 1:
            wait_time = (attempt + 1) * 2  # 점진적으로 대기 시간 증가
            print(f"{wait_time}초 후 재시도...")
            time.sleep(wait_time)

    return "API 요청이 모두 실패했습니다. 잠시 후 다시 시도해주세요.", None
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            print("\n=== 파일 업로드 요청 시작 ===")
            print("요청 데이터:", request.files)
            
            if 'file' not in request.files:
                print("파일이 요청에 없음")
                return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400
            
            file = request.files['file']
            print(f"파일 정보: {file.filename}, {file.content_type}")
            
            if file.filename == '':
                print("파일 이름이 비어있음")
                return jsonify({"error": "선택된 파일이 없습니다."}), 400
            
            if not allowed_file(file.filename):
                print(f"지원되지 않는 파일 형식: {file.filename}")
                return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400
            
            try:
                # 업로드 폴더 생성
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                # 파일 저장 (확장자 포함)
                filename = secure_filename(file.filename)
                orig_ext = os.path.splitext(filename)[1].lower()  # 원본 확장자 추출
                
                # 파일 타입에 따른 확장자 확인
                if file.content_type == 'image/png':
                    ext = '.png'
                elif file.content_type == 'image/jpeg':
                    ext = '.jpg'
                elif file.content_type == 'application/pdf':
                    ext = '.pdf'
                elif file.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                    ext = '.docx'
                else:
                    print(f"지원되지 않는 Content-Type: {file.content_type}")
                    return jsonify({"error": "지원되지 않는 파일 형식입니다."}), 400

                # 원본 파일명 유지하면서 확장자 처리
                if not orig_ext:
                    filename = filename + ext
                
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                print(f"파일 저장 경로: {filepath}")
                file.save(filepath)
                print("파일 저장 완료")
                
                # 텍스트 추출
                extracted_text = extract_text_from_file(filepath)
                if not extracted_text:
                    print("텍스트 추출 실패")
                    return jsonify({"error": "텍스트를 추출할 수 없습니다."}), 400
                
                print(f"추출된 텍스트 길이: {len(extracted_text)}")
                
                # AI 분석
                ai_analysis, conversation_history = analyze_with_deepseek(extracted_text)
                if not ai_analysis:
                    print("AI 분석 실패")
                    return jsonify({"error": "AI 분석에 실패했습니다."}), 400
                
                # 세션에 대화 기록 저장
                session['conversation_history'] = conversation_history
                
                print("처리 완료")
                return jsonify({
                    "original_text": extracted_text,
                    "ai_analysis": ai_analysis
                })
                
            except Exception as e:
                print(f"파일 처리 중 오류: {str(e)}")
                traceback.print_exc()
                return jsonify({"error": str(e)}), 500
                
            finally:
                # 임시 파일 삭제
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"임시 파일 삭제됨: {filepath}")
                except Exception as e:
                    print(f"임시 파일 삭제 실패: {filepath} - {str(e)}")
                    
        except Exception as e:
            print(f"요청 처리 중 오류: {str(e)}")
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
    
    return render_template('index.html')






@app.route('/chat', methods=['POST'])
def chat():
    try:
        if 'conversation_history' not in session:
            return jsonify({"error": "대화 기록이 없습니다. 먼저 문서를 업로드해주세요."}), 400
        
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({"error": "메시지가 없습니다."}), 400
        
        response, updated_history = analyze_with_deepseek(
            user_message,
            session['conversation_history']
        )
        
        if not response:
            return jsonify({"error": "응답 생성에 실패했습니다."}), 500
        
        session['conversation_history'] = updated_history
        
        return jsonify({
            "response": response
        })
        
    except Exception as e:
        print(f"채팅 처리 중 오류: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)