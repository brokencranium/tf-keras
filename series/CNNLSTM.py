import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt


def plot_series(time, series, format="-", start=0, end=None):
    plt.plot(time[start:end], series[start:end], format)


def trend(time, slope=0):
    return slope * time


def seasonal_pattern(season_time):
    return np.where(season_time < 0.4,
                    np.cos(season_time * 2 * np.pi),
                    1 / np.exp(3 * season_time))


def seasonality(time, period, amplitude=1, phase=0):
    season_time = ((time + phase) % period) / period
    return amplitude * seasonal_pattern(season_time)


def noise(time, noise_level=1, seed=None):
    rnd = np.random.RandomState(seed)
    return rnd.randn(len(time)) * noise_level


def windowed_dataset(series, window_size, batch_size, shuffle_buffer):
    series = tf.expand_dims(series, axis=-1)
    dataset = tf.data.Dataset.from_tensor_slices(series)
    dataset = dataset.window(window_size + 1, shift=1, drop_remainder=True)
    dataset = dataset.flat_map(lambda window: window.batch(window_size + 1))
    dataset = dataset.shuffle(shuffle_buffer)
    dataset = dataset.map(lambda window: (window[:-1], window[1:]))
    dataset = dataset.batch(batch_size).prefetch(1)
    return dataset


def model_forecast(model, series, window_size, batch_size):
    dataset = tf.data.Dataset.from_tensor_slices(series)
    dataset = dataset.window(window_size, shift=1, drop_remainder=True)
    dataset = dataset.flat_map(lambda window: window.batch(window_size))
    dataset = dataset.batch(batch_size).prefetch(1)
    forecast = model.predict(dataset)
    return forecast


if __name__ == '__main__':
    time = np.arange(4 * 365 + 1, dtype='float32')
    baseline = 10
    series = trend(time, 0.1)
    baseline = 10
    amplitude = 40
    slope = 0.05
    noise_level = 5

    # create series
    series = baseline + trend(time, slope) + seasonality(time, period=365, amplitude=amplitude)
    # add noise
    series += noise(time, noise_level, seed=42)

    split_time = 1000
    time_train = time[:split_time]
    x_train = series[:split_time]

    time_val = time[split_time:]
    x_val = series[split_time:]

    window_size = 20
    batch_size = 128
    shuffle_buffer_size = 1000

    tf.keras.backend.clear_session()
    tf.random.set_seed(52)
    np.random.seed(52)

    train_set = windowed_dataset(series=x_train,
                                 window_size=window_size,
                                 batch_size=batch_size,
                                 shuffle_buffer=shuffle_buffer_size)

    # Determine the best learning rate
    model = tf.keras.models.Sequential([
        tf.keras.layers.Conv1D(filters=32,
                               kernel_size=5,
                               strides=1,
                               padding='causal',
                               activation='relu',
                               input_shape=[None, 1]),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(32, return_sequences=True)),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(32, return_sequences=True)),
        tf.keras.layers.Dense(1),
        tf.keras.layers.Lambda(lambda x: x * 200)
    ])

    lr_schedule = tf.keras.callbacks.LearningRateScheduler(lambda epoch: 1e-8 * 10 ** (epoch / 20))
    optimizer = tf.keras.optimizers.SGD(lr=1e-8, momentum=0.9)
    model.compile(loss=tf.keras.losses.Huber(),
                  optimizer=optimizer,
                  metrics=[tf.keras.metrics.MAE])
    history = model.fit(train_set, epochs=10, callbacks=[lr_schedule])

    plt.semilogx(history.history["lr"], history.history["loss"])
    plt.axis([1e-8, 1e-4, 0, 30])

    tf.keras.backend.clear_session()
    tf.random.set_seed(51)
    np.random.seed(51)

    dataset = windowed_dataset(series=x_train,
                               window_size=window_size,
                               batch_size=batch_size,
                               shuffle_buffer=shuffle_buffer_size)

    # Train the model with the identified learning rate
    model = tf.keras.models.Sequential([
        tf.keras.layers.Conv1D(filters=32,
                               kernel_size=5,
                               strides=1,
                               padding='causal',
                               activation='relu',
                               input_shape=[None, 1]),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(32, return_sequences=True)),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(32, return_sequences=True)),
        tf.keras.layers.Dense(1),
        tf.keras.layers.Lambda(lambda x: x * 200.0)
    ])

    optimizer = tf.keras.optimizers.SGD(lr=5e-5, momentum=0.9)
    model.compile(loss=tf.keras.losses.Huber(),
                  optimizer=optimizer,
                  metrics=["mae"])
    history = model.fit(dataset, epochs=10)

    forecast = model_forecast(model, series[..., np.newaxis], window_size, batch_size)
    forecast = forecast[split_time - window_size:-1, -1, 0]

    plt.figure(figsize=(10, 6))
    plot_series(time_val, x_val)
    plot_series(time_val, forecast)

    print(tf.keras.metrics.mean_absolute_error(x_val, forecast).numpy())

    # Retrieve a list of list results on training and test data sets for each training epoch
    mae = history.history['mae']
    loss = history.history['loss']

    epochs = range(len(loss))  # Get number of epochs

    # Plot MAE and Loss
    plt.plot(epochs, mae, 'r')
    plt.plot(epochs, loss, 'b')
    plt.title('MAE and Loss')
    plt.xlabel("Epochs")
    plt.ylabel("Accuracy")
    plt.legend(["MAE", "Loss"])

    plt.figure()

    epochs_zoom = epochs[200:]
    mae_zoom = mae[200:]
    loss_zoom = loss[200:]

    # Plot Zoomed MAE and Loss
    plt.plot(epochs_zoom, mae_zoom, 'r')
    plt.plot(epochs_zoom, loss_zoom, 'b')
    plt.title('MAE and Loss')
    plt.xlabel("Epochs")
    plt.ylabel("Accuracy")
    plt.legend(["MAE", "Loss"])

    plt.figure()
    plt.show()
