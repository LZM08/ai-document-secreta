// 로딩 시 marked 설정
window.onload = function() {
    marked.setOptions({
        breaks: true,
        gfm: true,
        pedantic: false,
        sanitize: false,
        smartLists: true,
        smartypants: false
    });
};

let isProcessing = false;

function showAlert(message, type = 'error') {
    const alert = document.getElementById('alert');
    const alertMessage = document.getElementById('alert-message');
    alertMessage.textContent = message;
    
    alert.classList.remove('hidden');
    
    // 3초 후 알림 숨기기
    setTimeout(() => {
        alert.classList.add('hidden');
    }, 3000);
}

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('upload-button').disabled = true;
    document.getElementById('upload-button').classList.add('opacity-50');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('upload-button').disabled = false;
    document.getElementById('upload-button').classList.remove('opacity-50');
}

function uploadFile(event) {
    if (event) {
        event.preventDefault();  // 폼 기본 동작 방지
    }
    
    if (isProcessing) return;

    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];

    if (!file) {
        showAlert('파일을 선택해주세요.');
        return;
    }

    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
        showAlert('파일 크기가 10MB를 초과합니다.');
        return;
    }

    isProcessing = true;
    showLoading();

    const formData = new FormData();
    formData.append('file', file);

    console.log('업로드할 파일:', {
        name: file.name,
        type: file.type,
        size: file.size
    });

    axios.post('/', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
    .then(response => {
        console.log('서버 응답:', response.data);
        
        if (response.data.error) {
            throw new Error(response.data.error);
        }

        document.getElementById('original-text').textContent = response.data.original_text;
        document.getElementById('ai-analysis').innerHTML = marked.parse(response.data.ai_analysis);
        document.getElementById('results').classList.remove('hidden');
    })
    .catch(error => {
        console.error('업로드 실패:', error);
        const errorMessage = error.response?.data?.error || error.message || '파일 업로드 중 오류가 발생했습니다.';
        showAlert(errorMessage);
    })
    .finally(() => {
        isProcessing = false;
        hideLoading();
        fileInput.value = '';
    });
}

function sendQuestion() {
    if (isProcessing) return;

    const questionInput = document.getElementById('question-input');
    const question = questionInput.value.trim();
    
    if (!question) {
        showAlert('질문을 입력해주세요.');
        return;
    }

    isProcessing = true;
    const chatHistory = document.getElementById('chat-history');
    const questionButton = document.getElementById('question-button');
    questionButton.disabled = true;
    questionButton.classList.add('opacity-50');
    
    // 사용자 질문 추가
    const userQuestion = document.createElement('div');
    userQuestion.className = 'chat-message bg-gray-50 p-4 rounded-lg';
    userQuestion.innerHTML = `
        <p class="font-semibold text-gray-800">
            <i class="fas fa-user-circle mr-2"></i>
            질문
        </p>
        <p class="text-gray-700 ml-6 mt-1">${question}</p>
    `;
    chatHistory.appendChild(userQuestion);

    questionInput.value = '';

    // AI 응답 요청
    axios.post('/chat', {
        message: question
    })
    .then(response => {
        if (response.data.error) {
            throw new Error(response.data.error);
        }
        const aiResponse = document.createElement('div');
        aiResponse.className = 'chat-message bg-blue-50 p-4 rounded-lg';
        aiResponse.innerHTML = `
            <p class="font-semibold text-blue-800">
                <i class="fas fa-robot mr-2"></i>
                AI 응답
            </p>
            <div class="text-gray-700 ml-6 mt-1">${marked.parse(response.data.response)}</div>
        `;
        chatHistory.appendChild(aiResponse);
        aiResponse.scrollIntoView({ behavior: 'smooth' });
    })
    .catch(error => {
        console.error('질문 전송 실패:', error);
        const errorMessage = error.response?.data?.error || error.message || '질문 전송 중 오류가 발생했습니다.';
        showAlert(errorMessage);
    })
    .finally(() => {
        isProcessing = false;
        questionButton.disabled = false;
        questionButton.classList.remove('opacity-50');
    });
}

// DOM이 로드된 후 이벤트 리스너 설정
document.addEventListener('DOMContentLoaded', function() {
    // 파일 업로드 폼 제출 이벤트
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', uploadFile);
    }

    // 버튼 클릭 이벤트
    const uploadButton = document.getElementById('upload-button');
    if (uploadButton) {
        uploadButton.addEventListener('click', uploadFile);
    }

    const questionButton = document.getElementById('question-button');
    if (questionButton) {
        questionButton.addEventListener('click', sendQuestion);
    }

    // Enter 키로 질문 전송
    const questionInput = document.getElementById('question-input');
    if (questionInput) {
        questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !isProcessing) {
                sendQuestion();
            }
        });
    }

    // 파일 입력 변경 이벤트
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const maxSize = 10 * 1024 * 1024; // 10MB
                if (file.size > maxSize) {
                    showAlert('파일 크기가 10MB를 초과합니다.');
                    e.target.value = '';
                }
            }
        });
    }

    // 파일 드래그 앤 드롭 처리
    const dropZone = document.querySelector('label');
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('border-blue-400');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('border-blue-400');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-blue-400');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const fileInput = document.getElementById('file-input');
                if (fileInput) {
                    fileInput.files = files;
                }
            }
        });
    }
});