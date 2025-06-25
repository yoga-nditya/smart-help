import React, { useEffect, useRef, useState } from 'react';

const WebRTCClient = () => {
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const peerRef = useRef(null);
  const wsRef = useRef(null);
  const [roomId, setRoomId] = useState(null);

  useEffect(() => {
    const clientId = '1bfaswK8zZ';
    const clientSecret = 'JO7Ztf0Fp1VUQRgwWAi1Cr0SJQL3mUu1';
    const ws = new WebSocket(`ws://localhost:8000/ws/available-rooms?client_id=${clientId}&client_secret=${clientSecret}`);
    wsRef.current = ws;

    const peer = new RTCPeerConnection();
    peerRef.current = peer;

    peer.onicecandidate = (event) => {
      if (event.candidate) {
        ws.send(JSON.stringify({ type: 'candidate', candidate: event.candidate, room: roomId }));
      }
    };

    peer.ontrack = (event) => {
      if (remoteVideoRef.current) {
        remoteVideoRef.current.srcObject = event.streams[0];
      }
    };

    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'room_ready') {
        const extractedRoomId = data.UserRoleId?.toString();
        setRoomId(extractedRoomId);
        startCall(extractedRoomId);
      } else if (data.type === 'offer') {
        await peer.setRemoteDescription(new RTCSessionDescription(data));
        const answer = await peer.createAnswer();
        await peer.setLocalDescription(answer);
        ws.send(JSON.stringify({ ...answer, type: 'answer', room: data.room }));
      } else if (data.type === 'answer') {
        await peer.setRemoteDescription(new RTCSessionDescription(data));
      } else if (data.type === 'candidate') {
        await peer.addIceCandidate(new RTCIceCandidate(data.candidate));
      }
    };

    const startCall = async (room) => {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream;
      }
      stream.getTracks().forEach((track) => peer.addTrack(track, stream));

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      ws.send(JSON.stringify({ ...offer, type: 'offer', room }));
    };

    return () => {
      ws.close();
      peer.close();
    };
  }, []);

  return (
    <div className="flex flex-col items-center space-y-4">
      <h1 className="text-2xl font-bold">WebRTC Video Chat</h1>
      <video ref={localVideoRef} autoPlay muted playsInline className="w-64 h-48 bg-black rounded" />
      <video ref={remoteVideoRef} autoPlay playsInline className="w-64 h-48 bg-black rounded" />
      <p className="text-sm text-gray-600">Room ID: {roomId || 'Waiting for assignment...'}</p>
    </div>
  );
};

export default WebRTCClient;
