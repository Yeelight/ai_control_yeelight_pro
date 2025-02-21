let mediaRecorder;
let audioChunks = [];
let transcriptionText = ''; // Variable to store transcription text



document.getElementById('startButton').onclick = async () => {
    document.getElementById('recordingIndicator').classList.remove('hidden'); // Hide indicator

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
        document.getElementById('submitDiv').classList.remove('hidden'); // Show submit butt
        document.getElementById('startButton').classList.remove('hidden'); // Show start button
        document.getElementById('stopButton').classList.add('hidden'); // Hide stop button
    };

    mediaRecorder.start();
    document.getElementById('startButton').disabled = true;
    document.getElementById('stopButton').disabled = false;    

    
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
        console.log('Audio Path:', audioPath); // 调试信息，检查音频路径
        const audioElement = document.createElement('audio'); // 创建音频元素
        const logList = document.getElementById('logList');
        if (logList) {
            audioElement.src = audioPath; // 确保路径正确
            audioElement.controls = true; // 启用音频控件
            audioElement.autoplay = false; // 自动播放音频
            logList.appendChild(audioElement); // 将音频播放器添加到 logList 中
            logList.appendChild(document.createElement('br')); // Append a line break
        } else {
            console.error('Error: logList element not found');
        }

        const resultVedioDiv = document.getElementById("resultVedioDiv");
        if (resultVedioDiv) {
            const resultMessage = data.result_message; 
            resultVedioDiv.innerHTML = ''; // Clear existing audio components
            const audioElementClone = audioElement.cloneNode(true); // 克隆音频元素
            resultVedioDiv.appendChild(audioElementClone); // Append the audio player to the body
            resultVedioDiv.appendChild(document.createElement('br')); // Append a line break
            resultVedioDiv.append(resultMessage); // Append a line break
        } else {
            console.error('Error: resultVedioDiv element not found');
        }
    } else {
        console.error('Error:', data.message);
    }
}; 



document.getElementById('stopButton').onclick = () => {
    if (mediaRecorder) {
        mediaRecorder.stop();  // Stop recording
        mediaRecorder = null;  // Reset mediaRecorder
    }
    document.getElementById('startButton').disabled = false;
    document.getElementById('stopButton').disabled = true;  
    document.getElementById('recordingIndicator').classList.add('hidden'); // Hide indicator

};



const socket = io();  // Initialize SocketIO client

// Listen for log updates from the server
socket.on('log_update', function(data) {
    const logList = document.getElementById('logList');
    logList.innerHTML += data.message.replace(/\n/g, '<br>');  // Append log message to the list with line breaks
    logList.scrollTop = logList.scrollHeight;  // Scroll to the bottom
});

document.addEventListener('DOMContentLoaded', function() {
    fetch('/scan_and_connect')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                console.log('Connected to gateway:', data.connected_gateway);
                document.getElementById("connected-gateway").textContent = `已连接的网关: IP - ${data.connected_gateway}`;
                // 调用 /get_topology 获取拓扑信息
                return fetch('/get_topology');
            } else {
                throw new Error(data.message);
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // 创建表格
                const nodesTable = document.createElement('table');
                nodesTable.className = 'table';

                // 创建表头
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');
                const headers = ['#', '名称', '类型'];
                headers.forEach((headerText, index) => {
                    const header = document.createElement('th');
                    header.scope = 'col';
                    header.textContent = headerText;
                    headerRow.appendChild(header);
                });
                thead.appendChild(headerRow);
                nodesTable.appendChild(thead);

                // 填充表格数据
                const tbody = document.createElement('tbody');
                data.nodes.forEach((node, index) => {
                    const row = document.createElement('tr');
                    const indexCell = document.createElement('th');
                    indexCell.scope = 'row';
                    indexCell.textContent = index + 1;

                    const nameCell = document.createElement('td');
                    nameCell.textContent = node.name;

                    const typeCell = document.createElement('td');
                    typeCell.textContent = node.type_description;

                    row.appendChild(indexCell);
                    row.appendChild(nameCell);
                    row.appendChild(typeCell);
                    tbody.appendChild(row);
                });
                nodesTable.appendChild(tbody);

                // 清空并添加表格
                const nodesListContainer = document.getElementById('nodes-list');
                nodesListContainer.innerHTML = ''; // 清空之前的内容
                nodesListContainer.appendChild(nodesTable);
            } else {
                throw new Error(data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });

    const startButton = document.getElementById('startButton');
    const recordingModalElement = document.getElementById('recordingModal');

    if (startButton && recordingModalElement) {
        const recordingModal = new bootstrap.Modal(recordingModalElement);

        startButton.onclick = function() {
            recordingModal.show();
        };
    } else {
        console.error('Element not found.');
    }
});

function connectToGateway(gatewayIp) {
    fetch('/connect_gateway', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ gateway_ip: gatewayIp })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(data.message);
            location.reload();  // Reload to update the connected gateway display
        } else {
            console.error('Error connecting to gateway:', data.message);
        }
    })
    .catch(error => console.error('Error:', error));
}

