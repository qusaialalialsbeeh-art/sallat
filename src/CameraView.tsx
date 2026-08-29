import {
  AlertTriangle,
  Camera,
  RefreshCcw,
  ShieldCheck,
} from 'lucide-react';
import type { RefObject } from 'react';
import { useEffect } from 'react';
import type { CameraFacing } from './camera';
import { PoseCanvas } from './PoseCanvas';
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
    if (!video || !stream) {
      return;
    }
    video.srcObject = stream;
    void video.play().catch(() => undefined);
    return () => {
      video.srcObject = null;
    };
  }, [stream, videoRef]);
  return (
    <section
      style={{
        width: '100%',
        borderRadius: 16,
        overflow: 'hidden',
        background: '#000',
        border: '1px solid #333',
      }}
      aria-label="معاينة الكاميرا"
    >
      <div
        style={{
          position: 'relative',
          width: '100%',
          aspectRatio: '16 / 9',
          background: '#000',
          overflow: 'hidden',
        }}
      >
        {stream ? (
          <>
            <video
              ref={videoRef}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                display: 'block',
                transform:
                  facing === 'user'
                    ? 'scaleX(-1)'
                    : 'none',
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
            <div
              style={{
                position: 'absolute',
                top: 12,
                left: 12,
                right: 12,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                pointerEvents: 'none',
                zIndex: 100,
              }}
            >
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 7,
                  padding: '7px 10px',
                  borderRadius: 8,
                  background: 'rgba(0,0,0,.65)',
                  color: '#fff',
                  fontSize: 12,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: '#36d399',
                  }}
                />
                بث مباشر
              </span>
              <span
                style={{
                  padding: '7px 10px',
                  borderRadius: 8,
                  background: 'rgba(0,0,0,.65)',
                  color: '#fff',
                  fontSize: 12,
                }}
              >
                {facing === 'user'
                  ? 'الكاميرا الأمامية'
                  : 'الكاميرا الخلفية'}
              </span>
            </div>
          </>
        ) : (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: 20,
              color: '#fff',
            }}
          >
            <div>
              <div
                style={{
                  width: 64,
                  height: 64,
                  margin: '0 auto 16px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: '#222',
                }}
              >
                {loading ? (
                  <RefreshCcw
                    size={27}
                    style={{
                      animation:
                        'spin 1s linear infinite',
                    }}
                  />
                ) : (
                  <Camera size={27} />
                )}
              </div>
              <h2
                style={{
                  margin: '0 0 8px',
                  fontSize: 20,
                }}
              >
                {loading
                  ? 'جاري فتح الكاميرا'
                  : 'المعاينة متوقفة'}
              </h2>
              <p
                style={{
                  margin: 0,
                  opacity: 0.65,
                  lineHeight: 1.6,
                  fontSize: 14,
                }}
              >
                {loading
                  ? 'امنح Safari لحظات قليلة لتهيئة الكاميرا.'
                  : 'اضغط تشغيل الكاميرا لبدء المعاينة.'}
              </p>
            </div>
          </div>
        )}
        {error && (
          <div
            role="alert"
            style={{
              position: 'absolute',
              left: 12,
              right: 12,
              bottom: 12,
              zIndex: 200,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: 12,
              borderRadius: 10,
              background: 'rgba(90,20,20,.95)',
              color: '#fff',
              fontSize: 13,
            }}
          >
            <AlertTriangle
              size={17}
              style={{ flexShrink: 0 }}
            />
            <span style={{ flex: 1 }}>
              {error}
            </span>
            <button
              type="button"
              onClick={onRetry}
              disabled={loading}
              style={{
                border: '1px solid rgba(255,255,255,.25)',
                background: 'rgba(255,255,255,.1)',
                color: '#fff',
                borderRadius: 7,
                padding: '7px 10px',
                fontSize: 12,
              }}
            >
              إعادة المحاولة
            </button>
          </div>
        )}
      </div>
      <div
        style={{
          minHeight: 44,
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          background: '#171717',
          color: '#fff',
          fontSize: 12,
        }}
      >
        <span
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            opacity: 0.8,
          }}
        >
          <ShieldCheck size={14} />
          التحليل محلي على الجهاز
        </span>
        <span
          style={{
            opacity: 0.45,
            fontSize: 10,
            letterSpacing: 0.5,
          }}
        >
          YOLO26L / ONNX
        </span>
      </div>
    </section>
  );
}