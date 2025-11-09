from dotenv import load_dotenv
import os
import asyncio
from livekit import agents, rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram

load_dotenv()


async def entrypoint(ctx: JobContext):
    # Connect the agent to the room (audio only)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    print(f"✅ Agent connected to room: {ctx.room.name}")

    # Initialize Deepgram STT
    stt = deepgram.STT(
        model="nova-2",
        language="en-US",
    )

    # Wait for a participant to join
    participant = await ctx.wait_for_participant()
    print(f"👤 Participant joined: {participant.identity}")

    # Try to find an audio track immediately
    audio_track = None
    for publication in participant.track_publications.values():
        if publication.track and publication.track.kind == rtc.TrackKind.KIND_AUDIO:
            audio_track = publication.track
            break

    if not audio_track:
        print("⏳ Waiting for audio track...")

        @ctx.room.on("track_subscribed")
        def on_track(track: rtc.Track, *args):
            nonlocal audio_track
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                audio_track = track
                print("🎤 Audio track received!")
                asyncio.create_task(transcribe_audio(audio_track, stt, participant))
    else:
        print("🎤 Audio track already available!")
        await transcribe_audio(audio_track, stt, participant)


async def transcribe_audio(track: rtc.AudioTrack, stt, participant):
    print("🎧 Starting transcription...")
    audio_stream = rtc.AudioStream(track)
    stt_stream = stt.stream()

    async def send_audio():
        try:
                async for event in audio_stream:
                    # Try to extract frame and sample_rate from event
                    # If event has 'frame' and 'sample_rate' attributes, use them
                    frame = getattr(event, 'frame', event)
                    sample_rate = getattr(event, 'sample_rate', None)
                    # If sample_rate is present, set it as an attribute on frame
                    if sample_rate is not None:
                        # If frame is not an object, make a dict
                        if not hasattr(frame, 'sample_rate'):
                            # Assume frame is bytes or numpy array, wrap in dict
                            frame = {'data': frame, 'sample_rate': sample_rate}
                        else:
                            frame.sample_rate = sample_rate
                    stt_stream.push_frame(frame)
                await stt_stream.flush()
        except RuntimeError as e:
            if "input ended" in str(e):
                print("🔇 Audio stream ended, stopping transcription gracefully.")
            else:
                raise

    async def receive_transcription():
        async for event in stt_stream:
            if event.type == agents.stt.SpeechEventType.FINAL_TRANSCRIPT:
                text = event.alternatives[0].text
                if text.strip():
                    print(f"📝 Transcription: {text}")

    # Run both tasks concurrently and close stream after
    await asyncio.gather(send_audio(), receive_transcription())
    await stt_stream.aclose()
    print("✅ Transcription session closed.")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))