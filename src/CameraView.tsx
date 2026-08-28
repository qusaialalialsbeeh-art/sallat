import { AlertTriangle, Camera, RefreshCcw, ShieldCheck } from 'lucide-react';
import type { RefObject } from 'react';
import { useEffect } from 'react';
import type { CameraFacing } from '@/lib/camera';
import { PoseCanvas } from '@/components/PoseCanvas';

type CameraViewProps = {
  videoRef: RefObject<HTMLVideoElement | null>;
  stream: MediaStream | null;
  facing: CameraFacing;
  active: boolean;
  loading: boolean;
  error: string;
  onRetry: () => void;
  onFrame?: (latency: number) => void;
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
}: CameraViewProps) {
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !stream) return;
    video.srcObject = stream;
    void video.play().catch(() => undefined);
    return () => {
      video.srcObject = null;
    };
  }, [stream, videoRef]);

  return (
    <section className="camera-card fade-up" aria-label="معاينة الكاميرا">
      <div className="camera-stage">
        {stream ? (
          <>
            <video
              ref={videoRef}
              className={facing === 'user' ? 'mirrored' : ''}
              autoPlay
              muted
              playsInline
              aria-label="بث الكاميرا المباشر"
              data-testid="video-camera"
            />
            <PoseCanvas videoRef={videoRef} active={active} mirrored={facing === 'user'} onFrame={onFrame} />
            <div className="stage-scrim" />
            <div className="stage-topline">
              <span className="stage-label"><span className="status-dot live pulse" /> بث مباشر</span>
              <span className="stage-label">{facing === 'user' ? 'الأمامية' : 'الخلفية'}</span>
            </div>
            <div className="stage-bottomline">
              <span className="stage-corner" />
              <span className="mono" style={{ fontSize: 10, opacity: .72 }}>LOCAL / POSE</span>
              <span className="stage-corner bottom" />
            </div>
          </>
        ) : (
          <div className="camera-empty">
            <div>
              <div className="empty-orb">{loading ? <RefreshCcw className="pulse" size={27} /> : <Camera size={27} />}</div>
              <h2>{loading ? 'جاري فتح الكاميرا' : 'المعاينة متوقفة'}</h2>
              <p>{loading ? 'امنح Safari لحظات قليلة لتهيئة البث المحلي.' : 'ابدأ الجلسة لرؤية الكاميرا وطبقة الوضعية على جهازك.'}</p>
            </div>
          </div>
        )}
        {error && (
          <div className="stage-error" role="alert" data-testid="status-camera-error">
            <AlertTriangle size={17} />
            <span>{error}</span>
            <button type="button" onClick={onRetry} className="control-button dark small" data-testid="button-retry-camera">
              إعادة المحاولة
            </button>
          </div>
        )}
      </div>
      <div className="camera-toolbar">
        <span className="stage-label"><ShieldCheck size={14} /> لا يغادر الفيديو جهازك</span>
        <span className="mono" style={{ color: 'rgb(236 241 233 / .58)', fontSize: 10 }}>SECURE PREVIEW</span>
      </div>
    </section>
  );
}