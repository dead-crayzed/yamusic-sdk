# 🎵 Yandex Music SDK (yamusic-sdk)

> Простой и удобный интерфейс для работы с Яндекс.Музыкой на Python

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Beta-yellow.svg)

**yamusic-sdk** — это легковесная обёртка над официальным [`yandex-music-api`](https://github.com/MarshalX/yandex-music-api), предоставляющая удобный интерфейс для базовых операций с Яндекс.Музыкой: поиск треков, скачивание, управление лайками, работа с плейлистами и персональными рекомендациями.

---

## ✨ Возможности

- 🔐 **Авторизация** через OAuth-токен с поддержкой `.env` и файла `~/.yandex_music_token`
- 🔍 **Поиск** треков, артистов, альбомов и плейлистов
- 💾 **Скачивание треков** с автоматическим подбором битрейта (320/192/128/64 kbps)
- ❤️ **Управление лайками**: получение, добавление и удаление треков из избранного
- 🌊 **«Моя волна»**: получение персональных музыкальных рекомендаций
- 📋 **Работа с плейлистами**: получение списка, треков и скачивание плейлистов
- 🗑 **Управление файлами**: очистка скачанных треков
- ⚡ **Интерактивный режим** для быстрого тестирования команд

---

## 🚀 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/dead-crayzed/yamusic-sdk.git
cd yamusic-sdk
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

> Если файла `requirements.txt` нет, установите основные зависимости вручную:

```bash
pip install yandex-music python-dotenv requests urllib3
```

---

## ⚙️ Настройка

### Получение токена

1. Перейдите на [https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195c](https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195c)
2. Авторизуйтесь и скопируйте полученный токен

### Способы указания токена (по приоритету):

1. **Аргумент при инициализации**:
   ```python
   client = YandexMusicSimple(token="ваш_токен")
   ```

2. **Файл `.env` в корне проекта**:
   ```env
   YANDEX_MUSIC_TOKEN=ваш_токен
   MUSIC_DOWNLOAD_DIR=music  # опционально
   ```

3. **Файл `~/.yandex_music_token`**:
   ```bash
   echo "ваш_токен" > ~/.yandex_music_token
   ```

---

## 💻 Использование

### Базовый пример

```python
from yandex_simple import create_client

# Инициализация клиента
client = create_client()

# Поиск трека
results = client.search("Queen Bohemian Rhapsody", search_type="track", limit=3)
for track in results:
    artists = ", ".join(a.name for a in track.artists) if track.artists else "Unknown"
    print(f"{artists} — {track.title} [ID: {track.track_id}]")

# Скачивание трека
if results:
    path = client.download_track(results[0].track_id, bitrate=192)
    print(f"✅ Скачано: {path}")
```

### Работа с лайками

```python
# Получить лайкнутые треки
liked = client.get_liked_tracks(limit=10)

# Добавить трек в лайки
client.like_track("12345:67890")

# Скачать все лайкнутые треки (последние 5)
client.download_liked(limit=5)
```

### «Моя волна» (персональные рекомендации)

```python
# Получить рекомендации
wave_tracks = client.get_my_wave(count=5)

# Скачать треки из рекомендаций
client.download_my_wave(count=3)
```

### Работа с плейлистами

```python
# Получить список плейлистов пользователя
playlists = client.get_user_playlists()

# Получить треки из плейлиста
tracks = client.get_playlist_tracks(playlist_id=12345, user_id=98765)

# Скачать плейлист (первые 20 треков)
client.download_playlist(playlist_id=12345, limit=20)
```

### Интерактивный режим

Запустите тестовый скрипт для интерактивной работы:

```bash
python test_yandex_simple.py
```

Доступные команды:
- `search <запрос>` — поиск трека
- `like <track_id>` — лайкнуть трек
- `download <track_id>` — скачать трек
- `liked` — показать лайкнутые треки
- `exit` — выход

---

## 📚 Справочник по методам

### 🔽 Скачивание

| Метод | Описание | Параметры |
|-------|----------|-----------|
| `download_track(track_id, filename, codec, bitrate)` | Скачать один трек | `track_id`: ID трека, `bitrate`: 320/192/128/64 |
| `download_tracks_batch(track_ids, **kwargs)` | Скачать несколько треков | `track_ids`: список ID |
| `download_liked(limit, **kwargs)` | Скачать лайкнутые треки | `limit`: количество |
| `download_my_wave(count, **kwargs)` | Скачать треки из «Моей волны» | `count`: количество |
| `download_playlist(playlist_id, limit, **kwargs)` | Скачать плейлист | `playlist_id`: ID плейлиста |

### ❤️ Лайки

| Метод | Описание |
|-------|----------|
| `get_liked_tracks(limit)` | Получить список лайкнутых треков |
| `like_track(track_id)` | Добавить трек в лайки |
| `unlike_track(track_id)` | Убрать трек из лайков |

### 🌊 Рекомендации

| Метод | Описание |
|-------|----------|
| `get_my_wave(count)` | Получить треки из «Моей волны» |
| `send_wave_feedback(track_id, action)` | Отправить фидбэк в радио |

### 📋 Плейлисты

| Метод | Описание |
|-------|----------|
| `get_user_playlists()` | Получить список плейлистов пользователя |
| `get_playlist_tracks(playlist_id, user_id, limit)` | Получить треки из плейлиста |

### 🔍 Поиск

| Метод | Описание |
|-------|----------|
| `search(query, search_type, limit)` | Поиск по Яндекс.Музыке |
| `search_and_download(query, **kwargs)` | Найти и скачать первый результат |

### 🗑 Управление файлами

| Метод | Описание |
|-------|----------|
| `delete_downloaded(pattern)` | Удалить скачанные файлы |
| `clear_cache()` | Очистить кэш клиента |

### 🔧 Утилиты

| Метод | Описание |
|-------|----------|
| `is_authorized()` | Проверить авторизацию |
| `get_account_info()` | Получить информацию об аккаунте |

---

## 📁 Структура проекта

```
yamusic-sdk/
├── yandex_simple.py      # Основной модуль с классом YandexMusicSimple
├── test_yandex_simple.py # Демонстрационный скрипт с примерами
├── .gitignore            # Исключения для git
└── README.md             # Этот файл
```

---

## 🛠 Требования

- Python 3.8+
- Зависимости:
  - `yandex-music>=2.0`
  - `python-dotenv>=0.19`
  - `requests>=2.25`
  - `urllib3>=1.26`

---

## ⚠️ Важные замечания

> ⚠️ **Юридическое предупреждение**: Скачивание защищённого авторским правом контента может нарушать условия использования Яндекс.Музыки и законодательство вашей страны. Используйте данный инструмент только для личного некоммерческого использования и в рамках разрешённого законодательством.

- Токен Яндекс.Музыки является конфиденциальной информацией — не передавайте его третьим лицам
- При частых запросах возможно временное ограничение доступа (rate limiting)
- Некоторые треки могут быть недоступны для скачивания из-за лицензионных ограничений

---

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для вашей фичи (`git checkout -b feature/amazing-feature`)
3. Закоммитьте изменения (`git commit -m 'Add some amazing feature'`)
4. Запушьте ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

---

## 📄 Лицензия

Проект распространяется под лицензией [MIT](LICENSE).

---

## 🔗 Ссылки

- [Официальная документация yandex-music-api](https://yandex-music-api.readthedocs.io/)
- [Yandex OAuth](https://oauth.yandex.ru/)
- [Репозиторий на GitHub](https://github.com/dead-crayzed/yamusic-sdk/)

---

> 💡 **Совет**: Все скачанные файлы сохраняются в папку `music/` (или указанную в `MUSIC_DOWNLOAD_DIR`). Используйте `client.delete_downloaded()` для очистки.

<<<<<<< HEAD
**Happy listening! 🎧**

