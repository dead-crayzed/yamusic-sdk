"""
yandex_simple.py — простой интерфейс для yandex-music-api
Базовые функции: скачивание, лайки, Моя волна, плейлисты и т.д.

GitHub: https://github.com/dead-crayzed/yamusic-sdk/
"""

import os
import logging
import re
import time
from pathlib import Path
from typing import Optional, List, Union
from dotenv import load_dotenv

from yandex_music import Client
from yandex_music.exceptions import YandexMusicError, InvalidBitrateError

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def configure_http_session(timeout: int = 30, retries: int = 3):
    """
    Глобальная настройка HTTP-сессии для yandex-music-api.
    :param timeout: Таймаут подключения в секундах
    :param retries: Количество повторных попыток
    """
    retry_strategy = Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "HEAD", "OPTIONS"]
    )
    
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=20,
        pool_block=False
    )
    
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    # Monkey-patch для применения сессии в yandex-music-api
    try:
        import yandex_music.utils.request as ym_request
        original_init = ym_request.Request.__init__
        
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self._session = session
            self.timeout = timeout
        
        ym_request.Request.__init__ = patched_init
    except ImportError:
        logger.warning("⚠️ Не удалось применить настройки HTTP-сессии")
    
    return session


configure_http_session(timeout=30, retries=3)


class YandexMusicSimple:
    """Простой клиент для базовых операций с Яндекс.Музыкой."""
    
    def __init__(self, token: Optional[str] = None, download_dir: Optional[str] = None):
        """
        Инициализация клиента.
        
        :param token: OAuth-токен (приоритет: аргумент → .env → файл ~/.yandex_music_token)
        :param download_dir: Папка для скачанных треков (по умолчанию из .env или "music")
        """
        self.token = (
            token or 
            os.getenv("YANDEX_MUSIC_TOKEN") or 
            self._load_token_from_file()
        )
        
        self.download_dir = Path(
            download_dir or 
            os.getenv("MUSIC_DOWNLOAD_DIR", "music")
        )
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        if self.token:
            self.client = Client(token=self.token).init()
        else:
            self.client = Client().init()
        
        # Безопасное получение информации об аккаунте
        try:
            account = self.client.account_status().account
            self.user = account
            user_name = (
                getattr(account, 'display_name', None) or
                getattr(account, 'full_name', None) or
                f"{getattr(account, 'first_name', 'User')} {getattr(account, 'second_name', '')}".strip() or
                f"User#{account.uid}"
            )
            logger.info(f"✅ Авторизован как: {user_name}")
        except YandexMusicError:
            logger.warning("⚠️ Не удалось получить информацию об аккаунте (возможно, токен невалиден)")
            self.user = None

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
    
    @staticmethod
    def _parse_track_id(track_id: Union[str, int]) -> str:
        """Приводит ID трека к формату 'трек:альбом' или просто 'трек'."""
        track_id = str(track_id).strip()
        if ':' in track_id:
            return track_id
        return track_id

    @staticmethod
    def _parse_playlist_id(playlist_id: Union[str, int]) -> tuple:
        """
        Парсит ID плейлиста из формата 'uid:pid' или просто pid.
        Возвращает кортеж (user_id, playlist_id).
        """
        playlist_id = str(playlist_id).strip()
        if ':' in playlist_id:
            uid, pid = playlist_id.split(':', 1)
            return int(uid), int(pid)
        return None, int(playlist_id)
    
    # ─────────────────────────────────────────────────────
    # 🔽 СКАЧИВАНИЕ ТРЕКОВ
    # ─────────────────────────────────────────────────────
    
    def download_track(self, track_id: str, filename: Optional[str] = None, 
                    codec: str = 'mp3', bitrate: int = 192) -> Optional[str]:
        """Скачать трек с авто-подбором доступного битрейта."""
        try:
            track_id = self._parse_track_id(track_id)
            
            # Получаем объект трека
            tracks = self.client.tracks([track_id])
            if not tracks or not tracks[0]:
                logger.error(f"❌ Трек {track_id} не найден")
                return None
            
            track = tracks[0]
            if not track.available:
                logger.error(f"❌ Трек {track_id} недоступен")
                return None
            
            # Формируем имя файла
            if filename is None:
                artists = ", ".join(a.name for a in (track.artists or [])) or "Unknown"
                filename = f"{artists} - {track.title}.mp3"
                filename = "".join(c for c in filename if c.isalnum() or c in " -_.").strip()
                filename = re.sub(r'\s+', ' ', filename)
            
            filepath = self.download_dir / filename
            
            # Пробуем битрейты по приоритету
            bitrates = [bitrate] + [b for b in [320, 192, 128, 64] if b != bitrate]
            
            for br in bitrates:
                try:
                    result_path = track.download(
                        filename=str(filepath),
                        codec=codec,
                        bitrate_in_kbps=br
                    )
                    if br != bitrate:
                        logger.warning(f"⚠️ Использован фолбэк-битрейт {br} вместо {bitrate}")
                    logger.info(f"✅ Скачан: {result_path} ({br} kbps)")
                    return result_path
                except InvalidBitrateError:
                    continue
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка при битрейте {br}: {e}")
                    continue
            
            logger.error(f"❌ Трек {track_id} не доступен ни в одном из битрейтов")
            return None
            
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
            time.sleep(0.1)
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
                try:
                    full_track = short_track.fetch_track()
                    if full_track and full_track.available:
                        tracks.append(full_track)
                except Exception as e:
                    logger.debug(f"⚠️ Не удалось загрузить трек из лайков: {e}")
                    continue
            logger.info(f"📚 Получено {len(tracks)} лайкнутых треков")
            return tracks
        except Exception as e:
            logger.error(f"❌ Ошибка получения лайков: {e}")
            return []
    
    def like_track(self, track_id: str) -> bool:
        """Добавить трек в лайки."""
        try:
            track_id = self._parse_track_id(track_id)
            self.client.users_likes_tracks_add(track_id)
            logger.info(f"❤️ Трек {track_id} добавлен в лайки")
            return True
        except YandexMusicError as e:
            logger.error(f"❌ Ошибка лайка: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}")
            return False

    def unlike_track(self, track_id: str) -> bool:
        """Убрать трек из лайков."""
        try:
            track_id = self._parse_track_id(track_id)
            self.client.users_likes_tracks_remove(track_id)
            logger.info(f"💔 Трек {track_id} удалён из лайков")
            return True
        except YandexMusicError as e:
            logger.error(f"❌ Ошибка удаления лайка: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}")
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
        Получить треки из 'Моей волны'.
        Используем штатный метод rotor_station_tracks.
        """
        try:
            # 1. Основной способ: Rotor API
            # 'user:onyourwave' — это идентификатор "Моей волны"
            station_data = self.client.rotor_station_tracks('user:onyourwave')
            
            tracks = []
            if station_data and hasattr(station_data, 'sequence'):
                for item in station_data.sequence:
                    # В Rotor API трек лежит в item.track
                    track = item.track
                    if track and track.available:
                        tracks.append(track)
                    
                    if len(tracks) >= count:
                        break

            if tracks:
                logger.info(f"🌊 Получено {len(tracks)} треков из 'Моей волны'")
                return tracks

            # 2. Фолбэк: Персональный плейлист дня (более релевантно, чем просто лайки)
            logger.warning("⚠️ Rotor API пуст, пробуем 'Плейлист дня'")
            feed = self.client.feed()
            for lookup in feed.days[0].tracks_to_play:
                if len(tracks) >= count:
                    break
                track = lookup.track
                if track and track.available:
                    tracks.append(track)
            
            if tracks:
                return tracks

        except Exception as e:
            logger.error(f"❌ Ошибка получения рекомендаций: {e}")

        # 3. Экстренный фолбэк: Лайки (последний шанс)
        try:
            likes = self.client.users_likes_tracks()
            # Выбираем последние 20, чтобы быстрее найти доступные
            fallback_tracks = []
            for short_track in likes[:20]:
                track = short_track.fetch_track()
                if track and track.available:
                    fallback_tracks.append(track)
                if len(fallback_tracks) >= count:
                    break
            return fallback_tracks
        except Exception:
            return []

    
    def send_wave_feedback(self, track_id: str, action: str = 'play'):
        """
        Отправить фидбэк в радио (для улучшения рекомендаций).
        :param action: 'play', 'skip', 'like', 'dislike'
        """
        try:
            logger.info(f"📡 Фидбэк: трек {track_id}, действие {action}")
            # Реализация зависит от версии API
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
            uid = self.user.uid if self.user else None
            if not uid:
                logger.error("❌ Не удалось получить UID пользователя")
                return []
            playlists = self.client.users_playlists_list(uid)
            logger.info(f"📋 Найдено {len(playlists)} плейлистов")
            return playlists
        except Exception as e:
            logger.error(f"❌ Ошибка получения плейлистов: {e}")
            return []
        
    def get_playlist_tracks(self, playlist_id: Union[int, str], 
                            user_id: Optional[int] = None,
                            limit: Optional[int] = None) -> List:
        """
        Получить треки из конкретного плейлиста с поддержкой динамических плейлистов.
        :param limit: Ограничить количество возвращаемых треков
        """
        try:
            # Парсим ID
            if isinstance(playlist_id, str) and ':' in playlist_id:
                owner_uid, pid = map(int, playlist_id.split(':', 1))
            else:
                owner_uid, pid = None, int(playlist_id)
            
            user_id = user_id or owner_uid or (self.user.uid if self.user else None)
            if not user_id:
                logger.error("❌ Не указан owner_uid для плейлиста")
                return []
            
            # Получаем плейлист — API возвращает список при передаче списка kind
            playlists = self.client.users_playlists([pid], user_id)
            if not playlists or not isinstance(playlists, list) or not playlists[0]:
                logger.warning(f"⚠️ Плейлист {playlist_id} не найден")
                return []
            
            playlist = playlists[0]
            tracks = []
            
            # ✅ Ключевое исправление: для динамических плейлистов используем fetch_tracks()
            if hasattr(playlist, 'generated_playlist_type') and playlist.generated_playlist_type:
                # Это динамический плейлист — загружаем треки через специальный метод
                logger.info(f"🔄 Динамический плейлист '{playlist.title}', тип: {playlist.generated_playlist_type}")
                try:
                    # fetch_tracks() загружает треки динамического плейлиста
                    if hasattr(playlist, 'fetch_tracks'):
                        all_tracks = playlist.fetch_tracks()
                        tracks = [t for t in all_tracks if t and t.available]
                    else:
                        # Фолбэк: пробуем получить через tracks и fetch_track
                        for short_track in (playlist.tracks or []):
                            if not short_track:
                                continue
                            track = getattr(short_track, 'track', short_track)
                            if track and getattr(track, 'available', True):
                                if hasattr(track, 'fetch_track') and not hasattr(track, 'duration_ms'):
                                    track = track.fetch_track()
                                if track and track.available:
                                    tracks.append(track)
                except Exception as fetch_error:
                    logger.warning(f"⚠️ Не удалось загрузить треки динамического плейлиста: {fetch_error}")
                    # Фолбэк на обычные треки
                    for short_track in (playlist.tracks or []):
                        if not short_track:
                            continue
                        track = getattr(short_track, 'track', short_track)
                        if track and getattr(track, 'available', True):
                            if hasattr(track, 'fetch_track') and not hasattr(track, 'duration_ms'):
                                track = track.fetch_track()
                            if track and track.available:
                                tracks.append(track)
            else:
                # Обычный плейлист — обрабатываем треки напрямую
                for short_track in (playlist.tracks or []):
                    if not short_track:
                        continue
                    try:
                        track = getattr(short_track, 'track', short_track)
                        if track and getattr(track, 'available', True):
                            if hasattr(track, 'fetch_track') and not hasattr(track, 'duration_ms'):
                                track = track.fetch_track()
                            if track and track.available:
                                tracks.append(track)
                                if limit and len(tracks) >= limit:
                                    break
                    except Exception as e:
                        logger.debug(f"⚠️ Пропущен трек в плейлисте: {e}")
                        continue
            
            # Применяем лимит если указан
            if limit and len(tracks) > limit:
                tracks = tracks[:limit]
            
            logger.info(f"🎵 В плейлисте '{playlist.title}': {len(tracks)} треков")
            return tracks
            
        except YandexMusicError as e:
            logger.error(f"❌ API ошибка: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка получения плейлиста: {e}")
            return []
    
    def download_playlist(self, playlist_id: Union[int, str], 
                          limit: int = 20, **kwargs) -> List[str]:
        """Скачать треки из плейлиста."""
        tracks = self.get_playlist_tracks(playlist_id, limit=limit)
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
        logger.info("🧹 Кэш очищен (заглушка)")
    
    # ─────────────────────────────────────────────────────
    # 🔧 ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ
    # ─────────────────────────────────────────────────────
    
    def is_authorized(self) -> bool:
        """Проверить, авторизован ли клиент."""
        return bool(self.token and self.client and getattr(self.client, 'auth_token', None))
    
    def get_account_info(self) -> dict:
        """Получить информацию об аккаунте."""
        if not self.user:
            return {}
        try:
            return {
                'uid': self.user.uid,
                'display_name': getattr(self.user, 'display_name', None),
                'first_name': getattr(self.user, 'first_name', None),
                'second_name': getattr(self.user, 'second_name', None),
                'login': getattr(self.user, 'login', None),
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения инфо аккаунта: {e}")
            return {}


# ─────────────────────────────────────────────────────
# 🎯 УДОБНЫЕ АЛИАСЫ ДЛЯ БЫСТРОГО ДОСТУПА
# ─────────────────────────────────────────────────────

def create_client(token: Optional[str] = None, download_dir: Optional[str] = None) -> YandexMusicSimple:
    """
    Фабричная функция с поддержкой .env.
    Приоритет токена: аргумент → .env → ~/.yandex_music_token
    """
    load_dotenv()
    return YandexMusicSimple(token=token, download_dir=download_dir)


# Пример использования
if __name__ == "__main__":
    print("🎵 Yandex Music Simple Client\n")
    
    token = YandexMusicSimple.load_token()
    if not token:
        print("⚠️ Токен не найден. Проверьте .env или ~/.yandex_music_token")
    else:
        client = create_client()
        print("✅ Клиент готов к работе!")
        print("\nДоступные методы:")
        print("  • download_track(track_id)     — скачать трек")
        print("  • get_liked_tracks()           — получить лайки")
        print("  • download_liked(limit)        — скачать лайки")
        print("  • get_my_wave(count)           — Моя волна")
        print("  • search(query)                — поиск")
        print("  • get_playlist_tracks(id)      — треки плейлиста")
        print("  • like_track(track_id)         — лайкнуть")