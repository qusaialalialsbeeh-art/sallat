import tensorflow as tf
from tensorflow.keras import layers, models

IMG_SIZE = (224, 224)
BATCH_SIZE = 32
NUM_CLASSES = 4
EPOCHS = 10

DATASET_DIR = "dataset"


# ==========================================
# 1. تحميل بيانات الصور
# ==========================================

train_dataset = tf.keras.utils.image_dataset_from_directory(
    DATASET_DIR,
    validation_split=0.2,
    subset="training",
    seed=123,
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
)

validation_dataset = tf.keras.utils.image_dataset_from_directory(
    DATASET_DIR,
    validation_split=0.2,
    subset="validation",
    seed=123,
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
)


print("\nالفئات التي وجدها النظام:")
print(train_dataset.class_names)


# ==========================================
# 2. تحسين سرعة تحميل الصور
# ==========================================

AUTOTUNE = tf.data.AUTOTUNE

train_dataset = train_dataset.prefetch(
    buffer_size=AUTOTUNE
)

validation_dataset = validation_dataset.prefetch(
    buffer_size=AUTOTUNE
)


# ==========================================
# 3. تحميل MobileNetV2
# ==========================================

base_model = tf.keras.applications.MobileNetV2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights="imagenet"
)


# تجميد MobileNetV2
base_model.trainable = False


# ==========================================
# 4. بناء نموذج الصلاة الخاص بنا
# ==========================================

model = models.Sequential([
    layers.Input(shape=(224, 224, 3)),

    layers.Rescaling(
        1.0 / 127.5,
        offset=-1
    ),

    base_model,

    layers.GlobalAveragePooling2D(),

    layers.Dropout(0.2),

    layers.Dense(
        NUM_CLASSES,
        activation="softmax"
    )
])


# ==========================================
# 5. تجهيز النموذج للتدريب
# ==========================================

model.compile(
    optimizer=tf.keras.optimizers.Adam(
        learning_rate=0.001
    ),

    loss="sparse_categorical_crossentropy",

    metrics=["accuracy"]
)


# ==========================================
# 6. عرض معلومات النموذج
# ==========================================

model.summary()


# ==========================================
# 7. تدريب النموذج
# ==========================================

print("\n===================================")
print("بدء تدريب نموذج صلاتي...")
print("===================================\n")


history = model.fit(
    train_dataset,
    validation_data=validation_dataset,
    epochs=EPOCHS
)


# ==========================================
# 8. حفظ النموذج
# ==========================================

model.save("salati_model.keras")


print("\n===================================")
print("اكتمل التدريب بنجاح")
print("تم حفظ النموذج باسم:")
print("salati_model.keras")
print("===================================")