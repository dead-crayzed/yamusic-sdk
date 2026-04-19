#!/usr/bin/env python3
"""
test_yandex_simple.py — демонстрация работы YandexMusicSimple
"""

import sys
import time
from pathlib import Path
from yandex_simple import YandexMusicSimple, create_client


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"📌 {title}")
    print('='*60)


def print_track(track, index: int = None):
    """Красивый вывод информации о треке."""
    prefix = f"{index}. " if index is not None else ""
    artists = ", ".join(a.name for a in (track.artists or [])) if track.artists else "Unknown"
    print(f"{prefix}{artists} — {track.title} [ID: {track.track_id}]")


def main():
    print("🎵 Yandex Music Simple — Тестовый запуск\n")
    
    # 🔐 Инициализация клиента
    print("🔑 Загрузка токена...")
    client = create_client()
    
    if not client.token:
        print("❌ Ошибка: токен не найден!")
        print("💡 Проверьте .env или создайте ~/.yandex_music_token")
        return 1
    
    print(f"✅ Авторизован: {client.user.display_name or client.user.uid}")
    
    # 🔍 Тест 1: Поиск трека
    print_section("🔍 Тест поиска: 'Queen Bohemian Rhapsody'")
    results = client.search("Queen Bohemian Rhapsody", search_type="track", limit=3)
    if results:
        for i, track in enumerate(results, 1):
            print_track(track, i)
    else:
        print("⚠️ Ничего не найдено")
    
    # ❤️ Тест 2: Лайкнутые треки
    print_section("❤️ Тест лайков: последние 3 трека")
    liked = client.get_liked_tracks(limit=3)
    if liked:
        for i, track in enumerate(liked, 1):
            print_track(track, i)
    else:
        print("⚠️ Лайкнутые треки не найдены")
    
    # 🌊 Тест 3: Моя волна (рекомендации)
    print_section("🌊 Тест рекомендаций (аналог 'Моя волна')")
    wave = client.get_my_wave(count=3)
    if wave:
        for i, track in enumerate(wave, 1):
            print_track(track, i)
    else:
        print("⚠️ Не удалось получить рекомендации")
    
    # 📋 Тест 4: Плейлисты пользователя
    print_section("📋 Тест плейлистов")
    playlists = client.get_user_playlists()
    if playlists:
        for i, pl in enumerate(playlists[:5], 1):
            print(f"{i}. {pl.title} — {pl.track_count} треков [ID: {pl.playlist_id}]")
        
        # Попробуем получить треки из первого плейлиста
        first_pl = playlists[0]
        print(f"\n🎵 Треки из плейлиста '{first_pl.title}':")
        tracks = client.get_playlist_tracks(first_pl.playlist_id, first_pl.owner.uid)
        if tracks:
            for i, tr in enumerate(tracks[:5], 1):
                print_track(tr, i)
        else:
            print("⚠️ Не удалось загрузить треки плейлиста")
    else:
        print("⚠️ У пользователя нет плейлистов")
    
    # 💾 Тест 5: Скачивание (с подтверждением)
    print_section("💾 Тест скачивания")
    if results:
        sample_track = results[0]
        print(f"🎧 Готов скачать: {sample_track.title}")
        confirm = input("Скачать? (y/n): ").strip().lower()
        if confirm == 'y':
            path = client.download_track(sample_track.track_id, bitrate=128)
            if path:
                size = Path(path).stat().st_size / 1024 / 1024
                print(f"✅ Скачано: {path} ({size:.2f} MB)")
            else:
                print("❌ Ошибка скачивания")
        else:
            print("⏭ Пропущено")
    
    # 🗑 Тест 6: Управление файлами
    print_section("🗑 Управление файлами")
    downloaded = list(client.download_dir.glob("*.mp3"))
    print(f"📁 В папке '{client.download_dir}': {len(downloaded)} файлов")
    if downloaded:
        print("Примеры:")
        for f in downloaded[:3]:
            size_kb = f.stat().st_size / 1024
            print(f"  • {f.name} ({size_kb:.0f} KB)")
    
    # ⚡ Тест 7: Быстрые команды (интерактив)
    print_section("⚡ Интерактивный режим")
    print("Введите команду или 'exit' для выхода:")
    print("  search <запрос>     — поиск трека")
    print("  like <ID>           — лайкнуть трек")
    print("  download <ID>       — скачать трек")
    print("  liked               — показать лайки")
    
    while True:
        try:
            cmd = input("\n>>> ").strip()
            if cmd.lower() in ('exit', 'quit', 'q'):
                break
            elif cmd.startswith('search '):
                query = cmd[7:]
                res = client.search(query, limit=3)
                for i, t in enumerate(res, 1):
                    print_track(t, i)
            elif cmd.startswith('like '):
                tid = cmd[5:].strip()
                success = client.like_track(tid)
                print("✅ Лайк добавлен" if success else "❌ Ошибка")
            elif cmd.startswith('download '):
                tid = cmd[9:].strip()
                path = client.download_track(tid)
                print(f"✅ {path}" if path else "❌ Ошибка")
            elif cmd.lower() == 'liked':
                liked = client.get_liked_tracks(limit=5)
                for i, t in enumerate(liked, 1):
                    print_track(t, i)
            else:
                print("❓ Неизвестная команда")
        except KeyboardInterrupt:
            print("\n⏭ Выход из интерактива")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # ✅ Завершение
    print_section("✅ Тест завершён!")
    print("💡 Подсказки:")
    print("  • Все скачанные файлы в папке:", client.download_dir.absolute())
    print("  • Для очистки: client.delete_downloaded()")
    print("  • Документация API: https://yandex-music-api.readthedocs.io/")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)