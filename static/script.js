let mediaRecorder;
let audioChunks = [];
let transcriptionText = ''; // Variable to store transcription text

document.getElementById('openModalButton').onclick = () => {
    document.getElementById('recordingModal').classList.remove('hidden'); // Show modal
};

document.getElementById('closeModalButton').onclick = () => {
    document.getElementById('recordingModal').classList.add('hidden'); // Hide modal
};

document.getElementById('startButton').onclick = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = event => {
        audioChunks.push(event.data);
    };

    mediaRecorder.onstop = async () => {
        if (audioChunks.length === 0) {
            alert('上传至后端的音频为空，无声音'); // Alert if no audio was recorded
            return; // Exit if no audio
        }

        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        const audioUrl = URL.createObjectURL(audioBlob); // Create a URL for the audio blob
        const audioPlayer = document.createElement('audio'); // Create an audio element
        audioPlayer.src = audioUrl; // Set the source to the audio blob URL
        audioPlayer.controls = true; // Enable controls for playback
        const resultDiv = document.getElementById("resultDiv");
        resultDiv.innerHTML = ''; // Clear existing audio components
        resultDiv.appendChild(document.createElement('br')); // Append a line break
        resultDiv.appendChild(audioPlayer); // Append the audio player to the body

        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        const startTime = Date.now(); // Record the start time
        const timerInterval = setInterval(() => {
            const elapsedTime = Math.floor((Date.now() - startTime) / 1000); // Calculate elapsed time in seconds
            document.getElementById('transcription').innerText = `Processing with the Whisper local model... (${elapsedTime} seconds)`;
        }, 1000); // Update every second

        const response = await fetch('/transcribe', {
            method: 'POST',
            body: formData
        });
        clearInterval(timerInterval); // Clear the timer
        const data = await response.json();
        transcriptionText = data.text; // Save transcription text
        document.getElementById('transcription').innerText = "";
        document.getElementById('transcription').innerText = transcriptionText;
        document.getElementById('submitDiv').classList.remove('hidden'); // Show submit button
        audioChunks = [];  // Reset for the next recording
        document.getElementById('recordingIndicator').classList.add('hidden'); // Hide indicator
        document.getElementById('startButton').classList.remove('hidden'); // Show start button
        document.getElementById('stopButton').classList.add('hidden'); // Hide stop button
    };

    mediaRecorder.start();
    document.getElementById('recordingIndicator').classList.remove('hidden'); // Show indicator
    document.getElementById('startButton').classList.add('hidden'); // Hide start button
    document.getElementById('stopButton').classList.remove('hidden'); // Show stop button
};

document.getElementById('stopButton').onclick = () => {
    document.getElementById('recordingModal').classList.add('hidden');
    if (mediaRecorder) {
        mediaRecorder.stop();  // Stop recording
        mediaRecorder = null;  // Reset mediaRecorder
    }
};
document.getElementById('submitButton').onclick = async () => {
    // 添加 loading 效果
    const submitButton = document.getElementById('submitButton');
    submitButton.disabled = true; // 禁用按钮以防止重复提交
    submitButton.innerText = '提交中...'; // 更新按钮文本

    const response = await fetch('/submit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user_input: transcriptionText }) // Send transcription text
    });

    // 恢复按钮状态
    submitButton.disabled = false; // 启用按钮
    submitButton.innerText = '提交'; // 恢复按钮文本

    const data = await response.json();
    
    if (data.status === 'success') {
        const audioPath = data.audio_path; // 获取音频路径
        const logList = document.getElementById('logList');
        const audioElement = document.createElement('audio'); // 创建音频元素
        audioElement.src = audioPath; // 确保路径正确
        audioElement.controls = true; // 启用音频控件
        audioElement.autoplay = true; // 自动播放音频
        logList.appendChild(audioElement); // 将音频播放器添加到 logList 中
        logList.appendChild(document.createElement('br')); // Append a line break
    } else {
        console.error('Error:', data.message);
    }
}; 

const socket = io();  // Initialize SocketIO client

// Listen for log updates from the server
socket.on('log_update', function(data) {
    const logList = document.getElementById('logList');
    logList.innerHTML += data.message.replace(/\n/g, '<br>');  // Append log message to the list with line breaks
    logList.scrollTop = logList.scrollHeight;  // Scroll to the bottom
});



document.addEventListener('DOMContentLoaded', function() {
    fetch('/scan_gateways')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const gatewaysList = document.getElementById('gateways-list');
                const connectedGateway = document.getElementById('connected-gateway');
                
                // 解析已连接的网关信息
                const connectedGatewayInfo = data.connected_gateway;
                if (connectedGatewayInfo==undefined) {
                    connectedGateway.textContent = `已连接的网关: 无`;
                }else{
                    connectedGateway.textContent = `已连接的网关: IP - ${connectedGatewayInfo}`;
                }
                
                // 解析扫描到的网关信息
                data.gateways.forEach(gatewayInfo => {
                    const listItem = document.createElement('p');
                    listItem.textContent = `网关地址: IP - ${gatewayInfo.ip}, MAC - ${gatewayInfo.mac}, DID - ${gatewayInfo.did}`;
                    gatewaysList.appendChild(listItem);
                });
            } else {
                console.error('Error fetching gateways:', data.message);
            }
        })
        .catch(error => console.error('Error:', error));
});

