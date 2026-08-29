import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, RefreshCcw, ShieldCheck, ScanFace } from 'lucide-react';
import { CameraView } from './CameraView';
import {
  CameraAccessError,
  type CameraFacing,
  requestCameraStream,
  stopCameraStream,
} from './camera';
function App() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [facing, setFacing] =
    useState<CameraFacing>('environment');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    document.title = 'مختبر الصلاة — YOLO26L';
    return () => {
      stopCameraStream(stream);
    };
  }, [stream]);
  const startCamera = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const nextStream = await requestCameraStream(facing);
      setStream((previous) => {
        stopCameraStream(previous);
        return nextStream;
      });
    } catch (err) {
      if (err instanceof CameraAccessError) {
        setError(err.message);
      } else {
        setError('تعذر تشغيل الكاميرا. حاول مرة أخرى.');
      }
    } finally {
      setLoading(false);
    }
  }, [facing]);
  const stopCamera = useCallback(() => {
    setStream((current) => {
      stopCameraStream(current);
      return null;
    });
    setError('');
  }, []);
  const switchCamera = useCallback(async () => {
    const nextFacing: CameraFacing =
      facing === 'environment'
        ? 'user'
        : 'environment';
    setLoading(true);
    setError('');
    setStream((current) => {
      stopCameraStream(current);
      return null;
    });
    setFacing(nextFacing);
    try {
      const nextStream =
        await requestCameraStream(nextFacing);
      setStream(nextStream);
    } catch (err) {
      if (err instanceof CameraAccessError) {
        setError(err.message);
      } else {
        setError('تعذر تبديل الكاميرا.');
      }
    } finally {
      setLoading(false);
    }
  }, [facing]);
  return (
    <main
      dir="rtl"
      style={{
        minHeight: '100vh',
        background: '#111',
        color: '#fff',
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        padding: 16,
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          maxWidth: 900,
          margin: '0 auto',
        }}
      >
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            marginBottom: 20,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <ScanFace size={28} />
            <div>
              <h1
                style={{
                  margin: 0,
                  fontSize: 20,
                }}
              >
                مختبر الوضعية
              </h1>
              <div
                style={{
                  marginTop: 3,
                  fontSize: 11,
                  opacity: 0.6,
                  letterSpacing: 1,
                  direction: 'ltr',
                }}
              >
                YOLO26L POSE / STAGE 01
              </div>
            </div>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              fontSize: 12,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: stream ? '#36d399' : '#777',
                display: 'inline-block',
              }}
            />
            {stream ? 'الكاميرا تعمل' : 'جاهز'}
          </div>
        </header>
        <section>
          <div style={{ marginBottom: 16 }}>
            <div
              style={{
                fontSize: 13,
                opacity: 0.6,
                marginBottom: 6,
              }}
            >
              تحليل محلي على الجهاز
            </div>
            <h2
              style={{
                margin: 0,
                fontSize: 30,
                lineHeight: 1.2,
              }}
            >
              كاميرا + YOLO26L
              <br />
              بدون رفع الفيديو
            </h2>
            <p
              style={{
                marginTop: 10,
                opacity: 0.7,
                lineHeight: 1.7,
              }}
            >
              الكاميرا ونموذج YOLO26L يعملان داخل المتصفح
              باستخدام ONNX Runtime Web.
            </p>
          </div>
          <CameraView
            videoRef={videoRef}
            stream={stream}
            facing={facing}
            active={Boolean(stream)}
            loading={loading}
            error={error}
            onRetry={startCamera}
          />
          {error && (
            <div
              style={{
                marginTop: 12,
                padding: 12,
                borderRadius: 10,
                background: '#421b1b',
                color: '#ffb4b4',
              }}
            >
              {error}
            </div>
          )}
          <div
            style={{
              display: 'flex',
              gap: 10,
              flexWrap: 'wrap',
              marginTop: 16,
            }}
          >
            {!stream ? (
              <button
                type="button"
                onClick={startCamera}
                disabled={loading}
                style={buttonStyle}
              >
                {loading ? (
                  <>
                    <RefreshCcw size={16} />
                    جاري التشغيل...
                  </>
                ) : (
                  <>
                    <Camera size={16} />
                    تشغيل الكاميرا
                  </>
                )}
              </button>
            ) : (
              <button
                type="button"
                onClick={stopCamera}
                style={buttonStyle}
              >
                إيقاف الكاميرا
              </button>
            )}
            <button
              type="button"
              onClick={switchCamera}
              disabled={loading}
              style={buttonStyle}
            >
              تبديل الكاميرا
            </button>
          </div>
          <div
            style={{
              marginTop: 20,
              padding: 14,
              borderRadius: 12,
              background: '#1b1b1b',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 13,
              opacity: 0.8,
            }}
          >
            <ShieldCheck size={18} />
            <span>
              الفيديو والتحليل يعملان محلياً على الجهاز.
            </span>
          </div>
        </section>
      </div>
    </main>
  );
}
const buttonStyle: React.CSSProperties = {
  border: '1px solid #444',
  background: '#222',
  color: '#fff',
  borderRadius: 10,
  padding: '11px 16px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: 14,
};
export default App;