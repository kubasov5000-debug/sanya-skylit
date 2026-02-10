import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyaudio
import numpy as np
import wave
import os
import threading
import time
from datetime import datetime
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class WhineDetectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎤 Детектор скуления Сани")
        self.root.geometry("1000x700")
        
        # Инициализация переменных
        self.is_running = False
        self.whine_count = 0
        self.whine_volumes = []
        self.recordings_dir = "whine_recordings"
        self.is_recording = False
        self.audio_buffer = deque(maxlen=44100 * 5)
        self.sample_rate = 44100
        self.last_whine_time = 0
        
        # Создаем папку для записей
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)
        
        # Инициализация PyAudio
        try:
            self.p = pyaudio.PyAudio()
            self.stream = None
        except:
            self.p = None
            messagebox.showerror("Ошибка", "Не удалось инициализировать аудиосистему")
        
        # Настройка стилей
        self.setup_styles()
        
        # Создание интерфейса
        self.create_widgets()
        
        # Запуск обновления графика
        self.update_plot()
        
        # Обработка закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_styles(self):
        """Настройка стилей приложения"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Цветовая схема
        self.bg_color = "#2b2b2b"
        self.fg_color = "#ffffff"
        self.accent_color = "#4CAF50"
        self.warning_color = "#FF9800"
        self.danger_color = "#F44336"
        
        # Настройка цветов
        self.root.configure(bg=self.bg_color)
        style.configure('TFrame', background=self.bg_color)
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color, font=('Arial', 10))
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Counter.TLabel', font=('Arial', 48, 'bold'), foreground=self.accent_color)
        style.configure('Volume.TLabel', font=('Arial', 24))
        style.configure('TButton', font=('Arial', 10), padding=10)
        style.configure('Start.TButton', foreground='white', background=self.accent_color)
        style.configure('Stop.TButton', foreground='white', background=self.danger_color)
    
    def create_widgets(self):
        """Создание всех виджетов интерфейса"""
        # Основной контейнер
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="🎤 ДЕТЕКТОР СКУЛЕНИЯ САНИ", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Счетчик скулений
        counter_frame = ttk.Frame(main_frame)
        counter_frame.pack(pady=20)
        
        ttk.Label(counter_frame, text="СКУЛЕНИЙ:", font=('Arial', 14)).pack()
        self.count_label = ttk.Label(counter_frame, text="0", style='Counter.TLabel')
        self.count_label.pack()
        
        # Панель управления
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(pady=20)
        
        self.start_button = ttk.Button(
            control_frame, 
            text="▶ НАЧАТЬ ПРОСЛУШИВАНИЕ", 
            style='Start.TButton',
            command=self.start_detection
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            control_frame, 
            text="⏹ ОСТАНОВИТЬ", 
            style='Stop.TButton',
            command=self.stop_detection,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            control_frame,
            text="📁 ОТКРЫТЬ ПАПКУ С ЗАПИСЯМИ",
            command=self.open_recordings_folder
        ).pack(side=tk.LEFT, padx=5)
        
        # Индикаторы
        indicators_frame = ttk.Frame(main_frame)
        indicators_frame.pack(pady=20, fill=tk.X)
        
        # Громкость
        volume_frame = ttk.Frame(indicators_frame)
        volume_frame.pack(side=tk.LEFT, expand=True, padx=10)
        
        ttk.Label(volume_frame, text="ТЕКУЩАЯ ГРОМКОСТЬ:", font=('Arial', 11)).pack()
        self.volume_label = ttk.Label(volume_frame, text="0", style='Volume.TLabel')
        self.volume_label.pack()
        
        # Прогресс-бар громкости
        self.volume_bar = ttk.Progressbar(
            volume_frame, 
            length=200, 
            mode='determinate',
            maximum=3000
        )
        self.volume_bar.pack(pady=5)
        
        # Статус
        status_frame = ttk.Frame(indicators_frame)
        status_frame.pack(side=tk.LEFT, expand=True, padx=10)
        
        ttk.Label(status_frame, text="СТАТУС:", font=('Arial', 11)).pack()
        self.status_label = ttk.Label(
            status_frame, 
            text="⏸ Ожидание запуска", 
            font=('Arial', 12, 'bold'),
            foreground=self.warning_color
        )
        self.status_label.pack()
        
        # Порог чувствительности
        threshold_frame = ttk.Frame(main_frame)
        threshold_frame.pack(pady=10)
        
        ttk.Label(threshold_frame, text="ЧУВСТВИТЕЛЬНОСТЬ:", font=('Arial', 11)).pack()
        
        self.threshold_var = tk.IntVar(value=800)
        threshold_scale = ttk.Scale(
            threshold_frame,
            from_=300,
            to=2000,
            variable=self.threshold_var,
            orient=tk.HORIZONTAL,
            length=300
        )
        threshold_scale.pack(pady=5)
        
        self.threshold_label = ttk.Label(
            threshold_frame, 
            text=f"Порог: {self.threshold_var.get()}",
            font=('Arial', 10)
        )
        self.threshold_label.pack()
        
        threshold_scale.config(command=self.update_threshold_label)
        
        # График в реальном времени
        graph_frame = ttk.LabelFrame(main_frame, text="ГРАФИК ГРОМКОСТИ", padding=10)
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        self.create_graph(graph_frame)
        
        # Лог событий
        log_frame = ttk.LabelFrame(main_frame, text="СОБЫТИЯ", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        self.log_text = tk.Text(
            log_frame, 
            height=8,
            bg="#1a1a1a",
            fg=self.fg_color,
            font=('Courier New', 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.log_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)
    
    def create_graph(self, parent):
        """Создание графика"""
        self.fig = Figure(figsize=(8, 4), dpi=100, facecolor=self.bg_color)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1a1a1a')
        
        # Настройка осей
        self.ax.set_xlabel('Время (сек)', color=self.fg_color)
        self.ax.set_ylabel('Громкость', color=self.fg_color)
        self.ax.tick_params(colors=self.fg_color)
        
        # Линия графика
        self.line, = self.ax.plot([], [], color=self.accent_color, linewidth=2)
        self.ax.set_ylim(0, 3000)
        self.ax.set_xlim(0, 30)
        
        # Пороговая линия
        self.threshold_line = self.ax.axhline(
            y=self.threshold_var.get(), 
            color=self.danger_color, 
            linestyle='--', 
            alpha=0.7
        )
        
        # Область скуления
        self.whine_area = None
        
        # Встраиваем график в tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def update_graph(self, volume, is_whine=False):
        """Обновление графика"""
        x_data = list(self.line.get_xdata())
        y_data = list(self.line.get_ydata())
        
        # Добавляем новые данные
        if len(x_data) == 0:
            x_data.append(0)
            y_data.append(volume)
        else:
            x_data.append(x_data[-1] + 0.1)
            y_data.append(volume)
        
        # Ограничиваем количество точек
        if len(x_data) > 300:
            x_data = x_data[-300:]
            y_data = y_data[-300:]
        
        # Обновляем линию
        self.line.set_data(x_data, y_data)
        
        # Обновляем ось X
        self.ax.set_xlim(max(0, x_data[-1] - 30), max(30, x_data[-1]))
        
        # Обновляем пороговую линию
        self.threshold_line.set_ydata([self.threshold_var.get()] * 2)
        
        # Подсветка скулящих звуков
        if is_whine:
            if self.whine_area:
                self.whine_area.remove()
            
            # Добавляем область скуления
            self.whine_area = self.ax.axvspan(
                x_data[-1] - 0.1, x_data[-1], 
                alpha=0.3, color=self.warning_color
            )
        
        self.canvas.draw()
    
    def update_plot(self):
        """Периодическое обновление графика"""
        if self.is_running:
            # Обновляем график с текущей громкостью
            if hasattr(self, 'current_volume'):
                self.update_graph(self.current_volume)
        
        # Повторяем каждые 100 мс
        self.root.after(100, self.update_plot)
    
    def update_threshold_label(self, value):
        """Обновление метки порога"""
        self.threshold_label.config(text=f"Порог: {int(float(value))}")
    
    def log_event(self, message):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        
        # Ограничиваем лог 100 строками
        lines = self.log_text.get(1.0, tk.END).split('\n')
        if len(lines) > 100:
            self.log_text.delete(1.0, f"{len(lines)-100}.0")
    
    def save_recording(self):
        """Сохранение записи скулящего звука"""
        if len(self.audio_buffer) == 0:
            return None
        
        # Берем последние 3 секунды из буфера
        samples_needed = int(3.0 * self.sample_rate)
        buffer_array = np.array(list(self.audio_buffer)[-samples_needed:], dtype=np.int16)
        
        if len(buffer_array) == 0:
            return None
        
        # Создаем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(
            self.recordings_dir, 
            f"скуление_{self.whine_count:03d}_{timestamp}.wav"
        )
        
        # Нормализуем и сохраняем
        if np.max(np.abs(buffer_array)) > 0:
            buffer_array = np.int16(buffer_array / np.max(np.abs(buffer_array)) * 32767)
        
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(buffer_array.tobytes())
        
        return filename
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """Callback для обработки аудио"""
        try:
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            
            # Сохраняем в буфер
            self.audio_buffer.extend(audio_data)
            
            # Вычисляем громкость
            volume = np.abs(audio_data).mean()
            self.current_volume = volume
            
            # Обновляем интерфейс в основном потоке
            self.root.after(0, self.update_ui, volume)
            
            # Проверка на скуление
            current_time = time.time()
            
            if (volume > self.threshold_var.get() and 
                current_time - self.last_whine_time > 1.5 and 
                not self.is_recording):
                
                # Частотный анализ
                fft = np.abs(np.fft.rfft(audio_data.astype(np.float32)))
                freqs = np.fft.rfftfreq(len(audio_data), 1/self.sample_rate)
                
                # Проверяем высокие частоты
                high_mask = (freqs > 700) & (freqs < 2200)
                if np.any(high_mask):
                    high_energy = np.sum(fft[high_mask])
                    total_energy = np.sum(fft)
                    
                    if total_energy > 0 and (high_energy / total_energy) > 0.15:
                        # Обнаружено скуление!
                        self.whine_count += 1
                        self.last_whine_time = current_time
                        self.whine_volumes.append(volume)
                        
                        # Сохраняем запись
                        self.is_recording = True
                        filename = self.save_recording()
                        
                        # Обновляем интерфейс
                        self.root.after(0, self.on_whine_detected, volume, filename)
                        self.is_recording = False
                        
        except Exception as e:
            print(f"Ошибка в callback: {e}")
        
        return (in_data, pyaudio.paContinue)
    
    def update_ui(self, volume):
        """Обновление элементов интерфейса"""
        # Обновляем счетчик
        self.count_label.config(text=str(self.whine_count))
        
        # Обновляем громкость
        self.volume_label.config(text=f"{int(volume)}")
        self.volume_bar['value'] = min(volume, 3000)
        
        # Обновляем цвет прогресс-бара
        if volume > self.threshold_var.get():
            self.volume_bar.configure(style='danger.Horizontal.TProgressbar')
        else:
            self.volume_bar.configure(style='TProgressbar')
    
    def on_whine_detected(self, volume, filename):
        """Обработка обнаруженного скуления"""
        # Обновляем счетчик
        self.count_label.config(text=str(self.whine_count))
        
        # Добавляем в лог
        if filename:
            file_size = os.path.getsize(filename) / 1024
            self.log_event(f"🎯 Скулящий звук #{self.whine_count}! Громкость: {int(volume)}, Запись сохранена ({file_size:.1f} KB)")
        else:
            self.log_event(f"🎯 Скулящий звук #{self.whine_count}! Громкость: {int(volume)}")
        
        # Визуальная обратная связь
        self.count_label.configure(foreground=self.warning_color)
        self.root.after(300, lambda: self.count_label.configure(foreground=self.accent_color))
        
        # Обновляем график с подсветкой
        self.update_graph(volume, is_whine=True)
    
    def start_detection(self):
        """Запуск детекции"""
        if self.p is None:
            messagebox.showerror("Ошибка", "Аудиосистема не инициализирована")
            return
        
        # Находим микрофон
        device_id = None
        device_name = "Неизвестно"
        
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                try:
                    test_stream = self.p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=self.sample_rate,
                        input=True,
                        input_device_index=i,
                        frames_per_buffer=1024
                    )
                    test_stream.close()
                    device_id = i
                    device_name = info['name']
                    break
                except:
                    continue
        
        if device_id is None:
            messagebox.showerror("Ошибка", "Микрофон не найден")
            return
        
        # Открываем поток
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=1024,
                stream_callback=self.audio_callback
            )
            
            self.stream.start_stream()
            self.is_running = True
            
            # Обновляем интерфейс
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_label.config(
                text=f"▶ Прослушивание... ({device_name[:30]})", 
                foreground=self.accent_color
            )
            
            self.log_event(f"Запущено прослушивание с микрофона: {device_name}")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось запустить прослушивание: {str(e)}")
    
    def stop_detection(self):
        """Остановка детекции"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        self.is_running = False
        
        # Обновляем интерфейс
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="⏸ Остановлено", foreground=self.warning_color)
        
        self.log_event("Прослушивание остановлено")
    
    def open_recordings_folder(self):
        """Открыть папку с записями"""
        if os.path.exists(self.recordings_dir):
            os.startfile(self.recordings_dir) if os.name == 'nt' else os.system(f'open "{self.recordings_dir}"')
        else:
            messagebox.showinfo("Информация", "Папка с записями еще не создана")
    
    def on_closing(self):
        """Обработка закрытия приложения"""
        if self.is_running:
            self.stop_detection()
        
        if self.p:
            self.p.terminate()
        
        self.root.destroy()

def main():
    """Запуск приложения"""
    root = tk.Tk()
    app = WhineDetectorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()  