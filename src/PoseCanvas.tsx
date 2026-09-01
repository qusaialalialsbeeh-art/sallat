import { useEffect, useRef, useState, type RefObject } from "react";
import {
  detectPose,
  drawPoseOverlay,
  loadPoseModel,
  type PoseFrame,
} from "./pose";

type PoseCanvasProps = {
  videoRef: RefObject<HTMLVideoElement | null>;
  active: boolean;
  mirrored: boolean;
  onFrame?: (frame: PoseFrame) => void;
};

export function PoseCanvas({
  videoRef,
  active,
  mirrored,
  onFrame,
}: PoseCanvasProps) {
  const canvasRef =
    useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef =
    useRef<number | null>(null);
  const processingRef =
    useRef(false);
  const frameCallback =
    useRef(onFrame);
  const [debugMessage, setDebugMessage] =
    useState("جاري تهيئة مراقبة الوضعية...");
  const [debugError, setDebugError] =
    useState(false);
  frameCallback.current = onFrame;
  useEffect(() => {
    const canvas =
      canvasRef.current;
    const video =
      videoRef.current;
    if (!canvas || !video || !active) {
      return;
    }
    let stopped = false;
    const setStatus = (
      message: string,
      error = false,
    ) => {
      console.log(
        error
          ? `[POSE ERROR] ${message}`
          : `[POSE] ${message}`,
      );
      if (!stopped) {
        setDebugMessage(message);
        setDebugError(error);
      }
    };
    // ========================================================
    // CANVAS RESIZE
    // ========================================================
    const resizeCanvas = () => {
      const rect =
        canvas.getBoundingClientRect();
      const ratio =
        window.devicePixelRatio || 1;
      const width =
        Math.max(
          1,
          Math.round(
            rect.width * ratio,
          ),
        );
      const height =
        Math.max(
          1,
          Math.round(
            rect.height * ratio,
          ),
        );
      if (
        canvas.width !== width ||
        canvas.height !== height
      ) {
        canvas.width = width;
        canvas.height = height;
      }
    };
    resizeCanvas();
    window.addEventListener(
      "resize",
      resizeCanvas,
    );
    // ========================================================
    // START
    // ========================================================
    const start = async () => {
      try {
        setStatus(
          "1/5: تم تشغيل PoseCanvas",
        );
        // ======================================================
        // WAIT FOR VIDEO
        // ======================================================
        setStatus(
          "2/5: انتظار جاهزية الكاميرا...",
        );
        let attempts = 0;
        while (
          !stopped &&
          (
            video.videoWidth <= 0 ||
            video.videoHeight <= 0
          )
        ) {
          attempts++;
          if (attempts > 300) {
            throw new Error(
              "الكاميرا لم تعطِ أبعاد الفيديو.",
            );
          }
          await new Promise<void>(
            (resolve) => {
              requestAnimationFrame(
                () => resolve(),
              );
            },
          );
        }
        if (stopped) {
          return;
        }
        setStatus(
          `2/5: الكاميرا جاهزة ${video.videoWidth}×${video.videoHeight}`,
        );
        resizeCanvas();
        // ======================================================
        // LOAD MODEL (لا يوجد تحميل محلي، السيرفر جاهز)
        // ======================================================
        setStatus(
          "3/5: الاتصال بسيرفر التحليل...",
        );
        await loadPoseModel();
        if (stopped) {
          return;
        }
        setStatus(
          "4/5: السيرفر جاهز",
        );
        // ======================================================
        // DETECTION LOOP
        // ======================================================
        let frameCounter = 0;
        const processFrame =
          async () => {
            if (stopped) {
              return;
            }
            resizeCanvas();
            const context =
              canvas.getContext(
                "2d",
              );
            if (!context) {
              setStatus(
                "خطأ: تعذر إنشاء Canvas 2D",
                true,
              );
              return;
            }
            // ==================================================
            // PREVENT MULTIPLE INFERENCE
            // ==================================================
            if (
              processingRef.current
            ) {
              animationFrameRef.current =
                requestAnimationFrame(
                  () => {
                    void processFrame();
                  },
                );
              return;
            }
            // ==================================================
            // WAIT FOR CAMERA FRAME
            // ==================================================
            if (
              video.readyState <
                HTMLMediaElement.HAVE_CURRENT_DATA ||
              video.videoWidth <= 0 ||
              video.videoHeight <= 0
            ) {
              setStatus(
                "انتظار إطار الكاميرا...",
              );
              animationFrameRef.current =
                requestAnimationFrame(
                  () => {
                    void processFrame();
                  },
                );
              return;
            }
            processingRef.current =
              true;
            try {
              frameCounter++;
              const frame:
                PoseFrame | null =
                await detectPose(video);
              if (stopped) {
                return;
              }
              context.clearRect(
                0,
                0,
                canvas.width,
                canvas.height,
              );
              // ==================================================
              // SERVER RESPONDED
              // ==================================================
              if (frame && frame.detected) {
                const visiblePoints =
                  frame.points.filter(
                    (point) =>
                      point.confidence >=
                      0.4,
                  ).length;
                drawPoseOverlay(
                  context,
                  canvas.width,
                  canvas.height,
                  frame,
                  mirrored,
                );
                setStatus(
                  `5/5: ${frame.predictionAr} — ${visiblePoints}/17 نقطة — ثقة ${Math.round(
                    frame.classConfidence * 100,
                  )}% — ${frame.latency}ms`,
                );
                frameCallback.current?.(frame);
                // ==================================================
                // CONSOLE DEBUG
                // ==================================================
                if (
                  frameCounter % 30 ===
                  0
                ) {
                  console.log(
                    "POSE FRAME:",
                    {
                      predictionAr:
                        frame.predictionAr,
                      classConfidence:
                        frame.classConfidence,
                      personConfidence:
                        frame.personConfidence,
                      visiblePoints,
                      latency:
                        frame.latency,
                      videoWidth:
                        video.videoWidth,
                      videoHeight:
                        video.videoHeight,
                      points:
                        frame.points,
                    },
                  );
                }
              }
              // ==================================================
              // NO PERSON DETECTED
              // ==================================================
              else if (frame) {
                setStatus(
                  "5/5: السيرفر يعمل — لم يتم اكتشاف شخص",
                );
                frameCallback.current?.(frame);
              }
              // ==================================================
              // SERVER UNREACHABLE
              // ==================================================
              else {
                setStatus(
                  "تعذر الاتصال بسيرفر التحليل",
                  true,
                );
              }
            } catch (error) {
              const message =
                error instanceof Error
                  ? error.message
                  : String(error);
              console.error(
                "POSE FRAME ERROR:",
                error,
              );
              setStatus(
                `خطأ أثناء التحليل: ${message}`,
                true,
              );
            } finally {
              processingRef.current =
                false;
            }
            if (!stopped) {
              animationFrameRef.current =
                requestAnimationFrame(
                  () => {
                    void processFrame();
                  },
                );
            }
          };
        setStatus(
          "5/5: بدء تحليل الكاميرا...",
        );
        animationFrameRef.current =
          requestAnimationFrame(
            () => {
              void processFrame();
            },
          );
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : String(error);
        console.error(
          "POSE START FAILED:",
          error,
        );
        setStatus(
          `فشل تشغيل التحليل: ${message}`,
          true,
        );
      }
    };
    void start();
    // ========================================================
    // CLEANUP
    // ========================================================
    return () => {
      stopped = true;
      if (
        animationFrameRef.current !==
        null
      ) {
        cancelAnimationFrame(
          animationFrameRef.current,
        );
        animationFrameRef.current =
          null;
      }
      window.removeEventListener(
        "resize",
        resizeCanvas,
      );
      processingRef.current =
        false;
      const context =
        canvas.getContext("2d");
      context?.clearRect(
        0,
        0,
        canvas.width,
        canvas.height,
      );
    };
  }, [
    active,
    mirrored,
    videoRef,
  ]);
  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 50,
      }}
    />
  );
}