export type CameraFacing = 'environment' | 'user';

export class CameraAccessError extends Error {
  code: 'unsupported' | 'permission' | 'busy' | 'not-found' | 'unknown';

  constructor(
    code: CameraAccessError['code'],
    message: string,
  ) {
    super(message);
    this.name = 'CameraAccessError';
    this.code = code;
  }
}

export async function requestCameraStream(
  facing: CameraFacing,
): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new CameraAccessError(
      'unsupported',
      'يحتاج تشغيل الكاميرا إلى Safari حديث واتصال آمن (HTTPS).',
    );
  }

  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: facing },
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 30, max: 30 },
      },
    });
  } catch (error) {
    const name = error instanceof DOMException ? error.name : '';
    if (name === 'NotAllowedError' || name === 'SecurityError') {
      throw new CameraAccessError(
        'permission',
        'لم يتم السماح بالوصول إلى الكاميرا. افتح إعدادات Safari واسمح بالوصول ثم حاول مجدداً.',
      );
    }
    if (name === 'NotReadableError' || name === 'AbortError') {
      throw new CameraAccessError(
        'busy',
        'الكاميرا مشغولة بتطبيق آخر. أغلق التطبيقات التي تستخدمها ثم حاول مجدداً.',
      );
    }
    if (name === 'NotFoundError' || name === 'OverconstrainedError') {
      throw new CameraAccessError(
        'not-found',
        'تعذّر العثور على كاميرا متاحة في هذا الجهاز.',
      );
    }
    throw new CameraAccessError(
      'unknown',
      'حدث خطأ غير متوقع أثناء تشغيل الكاميرا. حاول مرة أخرى.',
    );
  }
}

export function stopCameraStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop());
}

export function getCameraLabel(stream: MediaStream | null) {
  const track = stream?.getVideoTracks()[0];
  const label = track?.label?.toLowerCase() ?? '';
  if (label.includes('front') || label.includes('facetime') || label.includes('user')) {
    return 'أمامية';
  }
  if (label.includes('back') || label.includes('rear') || label.includes('wide')) {
    return 'خلفية';
  }
  return 'كاميرا الجهاز';
}