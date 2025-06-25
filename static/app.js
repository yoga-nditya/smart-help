let localVideo = document.getElementById('localVideo');
let remoteVideo = document.getElementById('remoteVideo');
let chatBox = document.getElementById('chatBox');
let messageInput = document.getElementById('messageInput');

// Get room ID from URL
const urlParams = new URLSearchParams(window.location.search);
const roomId = urlParams.get('room') || 'default';

document.title = `Room: ${roomId}`;

let pc = new RTCPeerConnection({
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' }
  ]
});
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';

let ws = new WebSocket(`${protocol}://${location.host}/ws/${roomId}`);
console.log(ws);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'chat') {
    chatBox.innerHTML += `<div><b>Client:</b> ${data.message}</div>`;
    chatBox.scrollTop = chatBox.scrollHeight;
  } else if (data.type === 'offer') {
    pc.setRemoteDescription(new RTCSessionDescription(data.offer)).then(() => {
      return pc.createAnswer();
    }).then(answer => {
      return pc.setLocalDescription(answer);
    }).then(() => {
      ws.send(JSON.stringify({ type: 'answer', answer: pc.localDescription }));
    });
  } else if (data.type === 'answer') {
    pc.setRemoteDescription(new RTCSessionDescription(data.answer));
  } else if (data.type === 'candidate') {
    pc.addIceCandidate(new RTCIceCandidate(data.candidate));
  }
};

function sendMessage() {
  const msg = messageInput.value;
  if (msg) {
    ws.send(JSON.stringify({ type: 'chat', message: msg }));
    chatBox.innerHTML += `<div><b>You:</b> ${msg}</div>`;
    messageInput.value = '';
    chatBox.scrollTop = chatBox.scrollHeight;
  }
}

navigator.mediaDevices.getUserMedia({ video: true, audio: true })
  .then(stream => {
    localVideo.srcObject = stream;
    stream.getTracks().forEach(track => pc.addTrack(track, stream));
  });

pc.ontrack = (event) => {
  remoteVideo.srcObject = event.streams[0];
};

pc.onicecandidate = (event) => {
  if (event.candidate) {
    ws.send(JSON.stringify({ type: 'candidate', candidate: event.candidate }));
  }
};

ws.onopen = () => {
  pc.createOffer().then(offer => {
    return pc.setLocalDescription(offer);
  }).then(() => {
    ws.send(JSON.stringify({ type: 'offer', offer: pc.localDescription }));
  });
};
