import type { RefObject } from 'react';
import { useEffect } from 'react';
import type { CameraFacing } from './camera';
import { PoseCanvas } from './PoseCanvas';
import type { PoseFrame } from './pose';

type CameraViewProps = {
  videoRef: RefObject<HTMLVideoElement | null>;
  stream: MediaStream | null;
  facing: CameraFacing;
  active: boolean;
  loading: boolean;
  error: string;
  onRetry: () => void;
  onFrame?: (frame: PoseFrame) => void;
  frame?: PoseFrame | null;
};

export function CameraView({
  videoRef,
  stream,
  facing,
  active,
  loading,
  error,
  onRetry,
  onFrame,
  frame,
}: CameraViewProps) {
  useEffect(() => {
    const video = videoRef.current;

    if (!video || !stream) {
      return;
    }

    video.srcObject = stream;
    void video.play().catch(() => undefined);

    return () => {
      video.srcObject = null;
    };
  }, [stream, videoRef]);

  const statusText = !stream
    ? ''
    : !frame
      ? 'جاري المعاينة'
      : frame.detected
        ? `${frame.predictionAr} — ${Math.round(frame.classConfidence * 100)}%`
        : 'جاري التحليل...';

  return (
    <div className={`camera-view${!stream ? ' is-off' : ''}`} aria-label="معاينة الكاميرا">
      {stream ? (
        <>
          <video
            ref={videoRef}
            style={{
              transform: facing === 'user' ? 'scaleX(-1)' : 'none',
            }}
            autoPlay
            muted
            playsInline
            aria-label="بث الكاميرا المباشر"
          />

          <PoseCanvas
            videoRef={videoRef}
            active={active}
            mirrored={facing === 'user'}
            onFrame={onFrame}
          />

          <div className={`status-pill${statusText ? ' show' : ''}${frame && !frame.detected ? ' analyzing' : ''}`}>
            <span className="pulse" />
            <span>{statusText}</span>
          </div>
        </>
      ) : (
        <div className="off-hint">
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            {loading ? (
              <g style={{ transformOrigin: 'center', animation: 'spin 1s linear infinite' }}>
                <path d="M21 12a9 9 0 1 1-2.64-6.36" />
              </g>
            ) : (
              <>
                <path d="M4 8a2 2 0 0 1 2-2h1.2a2 2 0 0 0 1.66-.9l.8-1.2a2 2 0 0 1 1.67-.9h1.34a2 2 0 0 1 1.67.9l.8 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8Z" />
                <circle cx="12" cy="13" r="3.4" />
              </>
            )}
          </svg>
          <p>
            {loading
              ? 'جاري تهيئة الكاميرا...'
              : 'اضغط «بدء الكاميرا» لعرض المعاينة'}
          </p>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="error-banner"
          style={{ position: 'absolute', left: 12, right: 12, bottom: 12, zIndex: 200 }}
        >
          <span style={{ flex: 1 }}>{error}</span>
          <button type="button" className="retry-btn" onClick={onRetry} disabled={loading}>
            إعادة المحاولة
          </button>
        </div>
      )}
    </div>
  );
}