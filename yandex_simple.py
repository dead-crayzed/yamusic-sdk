"""
yandex_simple.py — простой интерфейс для yandex-music-api
Базовые функции: скачивание, лайки, Моя волна, плейлисты и т.д.
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Union
from dotenv import load_dotenv

from yandex_music import Client
from yandex_music.exceptions import YandexMusicError

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YandexMusicSimple:
    """Простой клиент для базовых операций с Яндекс.Музыкой."""
    
    def __init__(self, token: Optional[str] = None, download_dir: Optional[str] = None):
        """
        Инициализация клиента.
        
        :param token: OAuth-токен (приоритет: аргумент → .env → файл ~/.yandex_music_token)
        :param download_dir: Папка для скачанных треков (по умолчанию из .env или "music")
        """
        # 🔑 Загрузка токена с приоритетами
        self.token = (
            token or 
            os.getenv("YANDEX_MUSIC_TOKEN") or 
            self._load_token_from_file()
        )
        
        # 📁 Папка для скачивания
        self.download_dir = Path(
            download_dir or 
            os.getenv("MUSIC_DOWNLOAD_DIR", "music")
        )
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # 🎵 Инициализация клиента
        self.client = Client(self.token).init() if self.token else Client().init()
        
        # 👤 Безопасное получение имени пользователя
        account = self.client.account_status().account
        self.user = account
        
        # Формируем имя: пробуем display_name → full_name → first_name + second_name
        user_name = (
            getattr(account, 'display_name', None) or
            getattr(account, 'full_name', None) or
            f"{getattr(account, 'first_name', 'User')} {getattr(account, 'second_name', '')}".strip() or
            f"User#{account.uid}"
        )
        
        logger.info(f"✅ Авторизован как: {user_name}")

    @staticmethod
    def _load_token_from_file() -> Optional[str]:
        """Загружает токен из ~/.yandex_music_token (резервный способ)."""
        token_path = Path.home() / ".yandex_music_token"
        if token_path.exists():
            return token_path.read_text().strip()
        return None

    @staticmethod
    def load_token() -> Optional[str]:
        """Универсальная загрузка токена: .env → файл → None."""
        return (
            os.getenv("YANDEX_MUSIC_TOKEN") or 
            YandexMusicSimple._load_token_from_file()
        )
    
    # ─────────────────────────────────────────────────────
    # 🔽 СКАЧИВАНИЕ ТРЕКОВ
    # ─────────────────────────────────────────────────────
    
    def download_track(self, track_id: str, filename: Optional[str] = None, 
                       codec: str = 'mp3', bitrate: int = 192) -> Optional[str]:
        """
        Скачать трек по ID (формат: "трек:альбом" или просто "трек").
        
        :return: Путь к скачанному файлу или None при ошибке
        """
        try:
            track = self.client.tracks([track_id])[0]
            if not track or not track.available:
                logger.error(f"❌ Трек {track_id} недоступен")
                return None
            
            if filename is None:
                artists = ", ".join(a.name for a in track.artists) if track.artists else "Unknown"
                filename = f"{artists} - {track.title}.mp3"
            
            filepath = self.download_dir / filename
            track.download(str(filepath), codec=codec, bitrate_in_kbps=bitrate)
            logger.info(f"✅ Скачан: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"❌ Ошибка при скачивании: {e}")
            return None
    
    def download_tracks_batch(self, track_ids: List[str], 
                              codec: str = 'mp3', bitrate: int = 192) -> List[str]:
        """Скачать несколько треков. Возвращает список успешных путей."""
        results = []
        for tid in track_ids:
            path = self.download_track(tid, codec=codec, bitrate=bitrate)
            if path:
                results.append(path)
        return results
    
    # ─────────────────────────────────────────────────────
    # ❤️ ЛАЙКИ / ИЗБРАННОЕ
    # ─────────────────────────────────────────────────────
    
    def get_liked_tracks(self, limit: int = 50) -> List:
        """Получить список лайкнутых треков."""
        try:
            likes = self.client.users_likes_tracks()
            tracks = []
            for short_track in likes[:limit]:
                full_track = short_track.fetch_track()
                if full_track and full_track.available:
                    tracks.append(full_track)
            logger.info(f"📚 Получено {len(tracks)} лайкнутых треков")
            return tracks
        except Exception as e:
            logger.error(f"❌ Ошибка получения лайков: {e}")
            return []
    
    def like_track(self, track_id: str) -> bool:
        """Добавить трек в лайки."""
        try:
            self.client.users_likes_tracks_add(track_id, self.user.uid)
            logger.info(f"❤️ Трек {track_id} добавлен в лайки")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка лайка: {e}")
            return False
    
    def unlike_track(self, track_id: str) -> bool:
        """Убрать трек из лайков."""
        try:
            self.client.users_likes_tracks_remove(track_id, self.user.uid)
            logger.info(f"💔 Трек {track_id} удалён из лайков")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления лайка: {e}")
            return False
    
    def download_liked(self, limit: int = 10, **kwargs) -> List[str]:
        """Скачать последние лайкнутые треки."""
        tracks = self.get_liked_tracks(limit)
        return self.download_tracks_batch([t.track_id for t in tracks], **kwargs)
    
    # ─────────────────────────────────────────────────────
    # 🌊 МОЯ ВОЛНА (персональное радио)
    # ─────────────────────────────────────────────────────
    
    def get_my_wave(self, count: int = 10) -> List:
        """
        Получить треки из "Моей волны" (персонализированное радио).
        Использует Rotor API для генерации рекомендаций.
        """
        try:
            # Получаем станцию "Моя волна"
            station = self.client.rotor_station_result('user:onyourwave')
            
            # Получаем пачку треков
            sequence = self.client.rotor_station_tracks_result(
                station.station.id, 
                settings2=station.settings2,
                queue=station.sequence
            )
            
            tracks = []
            for batch in sequence.batch:
                track = batch.track
                if track and track.available:
                    tracks.append(track)
                    if len(tracks) >= count:
                        break
            
            logger.info(f"🌊 Получено {len(tracks)} треков из Моей волны")
            return tracks
        except Exception as e:
            logger.error(f"❌ Ошибка получения Моей волны: {e}")
            return []
    
    def send_wave_feedback(self, track_id: str, action: str = 'play'):
        """
        Отправить фидбэк в радио (для улучшения рекомендаций).
        :param action: 'play', 'skip', 'like', 'dislike'
        """
        try:
            # Упрощённая отправка — для полноценной работы нужен batchId и другие параметры
            logger.info(f"📡 Фидбэк: трек {track_id}, действие {action}")
            # В полной реализации здесь вызов client.rotor_station_feedback_*
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фидбэка: {e}")
    
    def download_my_wave(self, count: int = 5, **kwargs) -> List[str]:
        """Скачать треки из Моей волны."""
        tracks = self.get_my_wave(count)
        return self.download_tracks_batch([t.track_id for t in tracks], **kwargs)
    
    # ─────────────────────────────────────────────────────
    # 🎵 ПЛЕЙЛИСТЫ
    # ─────────────────────────────────────────────────────
    
    def get_user_playlists(self) -> List:
        """Получить список плейлистов пользователя."""
        try:
            playlists = self.client.users_playlists(self.user.uid)
            logger.info(f"📋 Найдено {len(playlists)} плейлистов")
            return playlists
        except Exception as e:
            logger.error(f"❌ Ошибка получения плейлистов: {e}")
            return []
    
    def get_playlist_tracks(self, playlist_id: Union[int, str], 
                            user_id: Optional[int] = None) -> List:
        """
        Получить треки из плейлиста.
        :param playlist_id: ID плейлиста
        :param user_id: ID владельца (по умолчанию — текущий пользователь)
        """
        try:
            user_id = user_id or self.user.uid
            playlist = self.client.users_playlists(playlist_id, user_id)
            
            tracks = []
            for short_track in playlist.tracks:
                if short_track.track:
                    tracks.append(short_track.track)
            
            logger.info(f"🎵 В плейлисте {playlist_id}: {len(tracks)} треков")
            return tracks
        except Exception as e:
            logger.error(f"❌ Ошибка получения плейлиста: {e}")
            return []
    
    def download_playlist(self, playlist_id: Union[int, str], 
                          limit: int = 20, **kwargs) -> List[str]:
        """Скачать треки из плейлиста."""
        tracks = self.get_playlist_tracks(playlist_id)[:limit]
        return self.download_tracks_batch([t.track_id for t in tracks], **kwargs)
    
    # ─────────────────────────────────────────────────────
    # 🔍 ПОИСК
    # ─────────────────────────────────────────────────────
    
    def search(self, query: str, search_type: str = 'track', limit: int = 10) -> List:
        """
        Поиск по Яндекс.Музыке.
        :param search_type: 'track', 'artist', 'album', 'playlist'
        """
        try:
            results = self.client.search(query, type_=search_type, nocorrect=False)
            
            if search_type == 'track' and results.tracks:
                items = results.tracks.results
            elif search_type == 'artist' and results.artists:
                items = results.artists.results
            elif search_type == 'album' and results.albums:
                items = results.albums.results
            elif search_type == 'playlist' and results.playlists:
                items = results.playlists.results
            else:
                items = []
            
            logger.info(f"🔍 Найдено {len(items)} результатов по запросу '{query}'")
            return items[:limit]
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []
    
    def search_and_download(self, query: str, **kwargs) -> Optional[str]:
        """Найти трек по запросу и скачать первый результат."""
        results = self.search(query, search_type='track', limit=1)
        if results:
            return self.download_track(results[0].track_id, **kwargs)
        return None
    
    # ─────────────────────────────────────────────────────
    # 🗑 УДАЛЕНИЕ / ОЧИСТКА
    # ─────────────────────────────────────────────────────
    
    def delete_downloaded(self, pattern: Optional[str] = None):
        """
        Удалить скачанные файлы.
        :param pattern: фильтр по имени файла (опционально)
        """
        count = 0
        for file in self.download_dir.glob(pattern or "*.*"):
            if file.is_file():
                file.unlink()
                count += 1
                logger.info(f"🗑 Удалён: {file.name}")
        logger.info(f"✅ Удалено файлов: {count}")
    
    def clear_cache(self):
        """Очистить кэш клиента (если используется)."""
        # В текущей версии библиотеки кэш не реализован явно,
        # но метод оставлен для совместимости
        logger.info("🧹 Кэш очищен (заглушка)")


# ─────────────────────────────────────────────────────
# 🎯 УДОБНЫЕ АЛИАСЫ ДЛЯ БЫСТРОГО ДОСТУПА
# ─────────────────────────────────────────────────────

def create_client(token: Optional[str] = None, download_dir: Optional[str] = None) -> YandexMusicSimple:
    """
    Фабричная функция с поддержкой .env.
    Приоритет токена: аргумент → .env → ~/.yandex_music_token
    """
    load_dotenv()  # на всякий случай, если не загружено ранее
    return YandexMusicSimple(token=token, download_dir=download_dir)


# Пример использования в __main__
if __name__ == "__main__":
    print("🎵 Yandex Music Simple Client\n")
    
    # Попытка авто-авторизации
    token = YandexMusicSimple.load_token()
    if not token:
        print("⚠️ Токен не найден. Запустите авторизацию:")
        print("   client = YandexMusicSimple.login_with_device_flow()")
    else:
        client = create_client()
        
        # Пример: скачать 3 последних лайкнутых трека
        # downloaded = client.download_liked(limit=3)
        # print(f"Скачано: {downloaded}")
        
        # Пример: получить треки из Моей волны
        # wave_tracks = client.get_my_wave(count=5)
        # for t in wave_tracks:
        #     print(f"🎧 {t.artists[0].name} - {t.title}")
        
        print("✅ Клиент готов к работе!")
        print("\nДоступные методы:")
        print("  • download_track(track_id)     — скачать трек")
        print("  • get_liked_tracks()           — получить лайки")
        print("  • download_liked(limit)        — скачать лайки")
        print("  • get_my_wave(count)           — Моя волна")
        print("  • download_my_wave(count)      — скачать из волны")
        print("  • search(query)                — поиск")
        print("  • get_playlist_tracks(id)      — треки плейлиста")
        print("  • like_track(track_id)         — лайкнуть")
        print("  • delete_downloaded()          — удалить файлы")