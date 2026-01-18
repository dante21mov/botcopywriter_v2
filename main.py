import asyncio
import logging
from telethon import TelegramClient, errors
from telethon.tl.types import MessageService

# ====== Настройки ======
API_ID = 25454498
API_HASH = "e3006b1e455fbe48a9355af42cd95c7d"
PHONE = "+79959270931"
PASSWORD = "212008"

SOURCE_CHANNEL = "https://t.me/emiltanfree"
TARGET_CHANNEL = "https://t.me/heyheyheypoo"

BATCH_SIZE = 20
BATCH_PAUSE = 1

# ====== Логирование ======
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ====== Класс работы с каналами ======
class ChannelCopier:
    def __init__(self, client):
        self.client = client

    async def _delete_existing_templates(self, target_entity):
        """Удаление всех существующих сообщений в целевом канале"""
        try:
            logger.info("Удаление существующих шаблонных сообщений...")
            deleted_count = 0
            async for msg in self.client.iter_messages(target_entity):
                if not isinstance(msg, MessageService) and (msg.message or msg.media):
                    try:
                        await self.client.delete_messages(target_entity, msg.id)
                        deleted_count += 1
                        logger.info(f"Удалено шаблонное сообщение {msg.id}")
                        await asyncio.sleep(0.1)  # Небольшая пауза между удалениями
                    except errors.FloodWaitError as e:
                        logger.warning(f"FloodWait {e.seconds}s")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        logger.error(f"Ошибка при удалении шаблона {msg.id}: {e}")
            logger.info(f"Все шаблонные сообщения удалены. Удалено: {deleted_count} сообщений")
        except Exception as e:
            logger.error(f"Ошибка при удалении шаблонов: {e}")

    async def _edit_template_message(self, template_msg, source_msg, target):
        """Вспомогательная функция для редактирования одного сообщения"""
        try:
            text = source_msg.text or ""

            if source_msg.media:
                try:
                    await self.client.edit_message(
                        entity=target,
                        message=template_msg.id,
                        text=text,
                        file=source_msg.media
                    )
                    logger.info(f"Шаблон {template_msg.id} отредактирован (медиа+текст)")
                except Exception as e:
                    if "You tried to send media of different types in an album" in str(e):
                        logger.warning(f"Пропускаем медиа из-за разных типов")
                        # Пытаемся отправить только текст
                        await self.client.edit_message(
                            entity=target,
                            message=template_msg.id,
                            text=text + "\n\n[Медиа недоступно для переноса]"
                        )
                    else:
                        raise e
            else:
                await self.client.edit_message(
                    entity=target,
                    message=template_msg.id,
                    text=text
                )
                logger.info(f"Шаблон {template_msg.id} отредактирован (текст)")

            # Пауза между редактированием
            await asyncio.sleep(0.1)

        except errors.FloodWaitError as e:
            logger.warning(f"FloodWait: ждём {e.seconds} сек")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Ошибка при редактировании шаблона {template_msg.id}: {e}")

    async def copy_old_messages(self):
        """Копирование всех старых сообщений с удалением шаблонов"""
        source = await self.client.get_entity(SOURCE_CHANNEL)
        target = await self.client.get_entity(TARGET_CHANNEL)

        # Сначала удаляем все существующие шаблоны
        await self._delete_existing_templates(target)

        # Затем копируем сообщения
        copied_count = 0
        async for msg in self.client.iter_messages(source, reverse=True):
            if msg.message or msg.media:
                try:
                    if msg.media:
                        await self.client.send_file(target, msg.media, caption=msg.text or "")
                    else:
                        await self.client.send_message(target, msg.text or "")
                    copied_count += 1
                    logger.info(f"Скопировано сообщение {msg.id}")

                    # Небольшая пауза между отправками
                    await asyncio.sleep(0.1)

                except errors.FloodWaitError as e:
                    logger.warning(f"FloodWait {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Ошибка при копировании сообщения {msg.id}: {e}")

        logger.info(f"Копирование старых сообщений завершено. Скопировано: {copied_count} сообщений")

    async def batch_copy_old_messages(self):
        """Пакетная отправка старых сообщений с удалением шаблонов"""
        source = await self.client.get_entity(SOURCE_CHANNEL)
        target = await self.client.get_entity(TARGET_CHANNEL)

        # Сначала удаляем все существующие шаблоны
        await self._delete_existing_templates(target)

        # Затем копируем сообщения
        batch = [msg async for msg in self.client.iter_messages(source, reverse=True) if msg.message or msg.media]

        copied_count = 0
        for i, msg in enumerate(batch):
            try:
                if msg.media:
                    await self.client.send_file(target, msg.media, caption=msg.text or "")
                else:
                    await self.client.send_message(target, msg.text or "")
                copied_count += 1
                logger.info(f"Скопировано сообщение {i + 1}/{len(batch)} (ID: {msg.id})")

                # Пауза между сообщениями для избежания флуда
                if (i + 1) % BATCH_SIZE == 0:
                    logger.info(f"Пауза {BATCH_PAUSE} секунд после {BATCH_SIZE} сообщений")
                    await asyncio.sleep(BATCH_PAUSE)
                else:
                    await asyncio.sleep(0.1)

            except errors.FloodWaitError as e:
                logger.warning(f"FloodWait {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Ошибка при копировании сообщения {msg.id}: {e}")

        logger.info(f"Пакетная отправка завершена. Скопировано: {copied_count}/{len(batch)} сообщений")

    async def copy_with_templates(self):
        """Редактирование существующих шаблонных постов с равномерным распределением"""
        source = await self.client.get_entity(SOURCE_CHANNEL)
        target = await self.client.get_entity(TARGET_CHANNEL)

        # Собираем шаблонные сообщения
        template_messages = []
        async for msg in self.client.iter_messages(target, reverse=True):
            if not isinstance(msg, MessageService) and (msg.message or msg.media):
                template_messages.append(msg)

        # Собираем исходные сообщения
        source_messages = [msg async for msg in self.client.iter_messages(source, reverse=True) if
                           msg.message or msg.media]

        template_count = len(template_messages)
        source_count = len(source_messages)

        if template_count == 0:
            logger.error("В целевом канале нет сообщений для редактирования!")
            return

        if source_count == 0:
            logger.error("В исходном канале нет сообщений!")
            return

        logger.info(f"Шаблонов в целевом канале: {template_count}")
        logger.info(f"Сообщений в исходном канале: {source_count}")

        # ВАЖНО: Определяем, сколько шаблонов оставить
        # Оставляем минимум: либо все шаблоны, либо количество из источника
        keep_count = min(template_count, source_count)

        if source_count >= template_count:
            # Если исходных сообщений больше или равно шаблонам
            # Берем последние N сообщений из источника (где N = количество шаблонов)
            source_messages_to_use = source_messages[-keep_count:]

            for i in range(keep_count):
                template_msg = template_messages[i]
                source_msg = source_messages_to_use[i]
                await self._edit_template_message(template_msg, source_msg, target)

            logger.info(f"Все шаблоны заменены. Использовано сообщений: {keep_count}")

        else:
            # Если исходных сообщений МЕНЬШЕ шаблонов
            # Равномерно распределяем их по каналу
            logger.info("Равномерное распределение сообщений по каналу...")

            # Создаем список индексов для равномерного распределения
            import math
            step = (template_count - 1) / max(1, (source_count - 1)) if source_count > 1 else 0

            edited_indices = set()  # Запоминаем какие шаблоны отредактировали

            for i in range(source_count):
                # Вычисляем индекс шаблона для замены (равномерно распределяем)
                if source_count == 1:
                    template_idx = template_count // 2  # Если одно сообщение - ставим в середину
                else:
                    template_idx = int(round(i * step))

                # Проверяем границы
                if template_idx >= template_count:
                    template_idx = template_count - 1

                template_msg = template_messages[template_idx]
                source_msg = source_messages[i]

                logger.info(f"Замена {i + 1}/{source_count}: шаблон {template_idx + 1}/{template_count}")

                await self._edit_template_message(template_msg, source_msg, target)
                edited_indices.add(template_idx)

            # Удаляем неиспользованные шаблоны (те, которые не были отредактированы)
            deleted_count = 0
            for i, template_msg in enumerate(template_messages):
                if i not in edited_indices:
                    try:
                        await self.client.delete_messages(target, template_msg.id)
                        logger.info(f"Удален неиспользованный шаблон {template_msg.id}")
                        deleted_count += 1
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.error(f"Ошибка при удалении шаблона {template_msg.id}: {e}")

            logger.info(f"Равномерное распределение завершено. Удалено неиспользованных шаблонов: {deleted_count}")

        logger.info("Редактирование завершено успешно!")

    async def copy_with_templates_simple(self):
        """Простое редактирование (старый метод - заменяет первые посты)"""
        source = await self.client.get_entity(SOURCE_CHANNEL)
        target = await self.client.get_entity(TARGET_CHANNEL)

        template_messages = []
        async for msg in self.client.iter_messages(target, reverse=True):
            if not isinstance(msg, MessageService) and (msg.message or msg.media):
                template_messages.append(msg)

        source_messages = [msg async for msg in self.client.iter_messages(source, reverse=True) if
                           msg.message or msg.media]

        count = min(len(template_messages), len(source_messages))
        logger.info(f"Будет отредактировано {count} шаблонных сообщений")

        edited_count = 0
        for i in range(count):
            template_msg = template_messages[i]
            source_msg = source_messages[i]

            try:
                text = source_msg.text or ""

                if source_msg.media:
                    try:
                        await self.client.edit_message(
                            entity=target,
                            message=template_msg.id,
                            text=text,
                            file=source_msg.media
                        )
                        logger.info(
                            f"Шаблон {template_msg.id} отредактирован (медиа+текст) из сообщения {source_msg.id}")
                        edited_count += 1
                    except Exception as e:
                        if "You tried to send media of different types in an album" in str(e):
                            logger.warning(f"Пропускаем сообщение {source_msg.id} из-за разных типов медиа")
                            continue
                        else:
                            raise e
                else:
                    await self.client.edit_message(
                        entity=target,
                        message=template_msg.id,
                        text=text
                    )
                    logger.info(f"Шаблон {template_msg.id} отредактирован (текст) из сообщения {source_msg.id}")
                    edited_count += 1

                # Пауза между редактированием
                await asyncio.sleep(0.1)

            except errors.FloodWaitError as e:
                logger.warning(f"FloodWait: ждём {e.seconds} сек")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Ошибка при редактировании шаблона {template_msg.id}: {e}")

        # Удаляем лишние шаблоны
        deleted_count = 0
        if len(template_messages) > len(source_messages):
            for extra_msg in template_messages[len(source_messages):]:
                try:
                    await self.client.delete_messages(target, extra_msg.id)
                    logger.info(f"Удалено лишнее сообщение-шаблон {extra_msg.id}")
                    deleted_count += 1
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Ошибка при удалении лишнего шаблона {extra_msg.id}: {e}")

        logger.info(
            f"Редактирование шаблонных сообщений завершено. Отредактировано: {edited_count}, удалено лишних: {deleted_count}")

    async def list_all_media_ids(self):
        """Вывод всех media_id для фото и документов"""
        target = await self.client.get_entity(TARGET_CHANNEL)
        logger.info(f"Сбор всех media_id из {TARGET_CHANNEL}")
        media_count = 0
        async for msg in self.client.iter_messages(target):
            media = msg.media
            if not media:
                continue

            media_id = None
            if getattr(media, "document", None):
                media_id = media.document.id
            elif getattr(media, "photo", None):
                media_id = media.photo.id

            if media_id:
                print(f"Сообщение {msg.id}: media_id={media_id}")
                media_count += 1

        logger.info(f"Найдено {media_count} медиа-сообщений")

    async def delete_media_by_id(self, target_media_id):
        """Удаление конкретного медиа по media_id"""
        target = await self.client.get_entity(TARGET_CHANNEL)
        deleted = False
        async for msg in self.client.iter_messages(target):
            media = msg.media
            if not media:
                continue

            media_id = None
            if getattr(media, "document", None):
                media_id = media.document.id
            elif getattr(media, "photo", None):
                media_id = media.photo.id

            if media_id == target_media_id:
                try:
                    await self.client.delete_messages(target, msg.id)
                    logger.info(f"Удалено сообщение {msg.id} с медиа {media_id}")
                    deleted = True
                    break
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения {msg.id}: {e}")

        if not deleted:
            logger.warning(f"Медиа с ID {target_media_id} не найдено")


# ====== Основная функция ======
async def main():
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start(phone=PHONE, password=PASSWORD)
    me = await client.get_me()
    logger.info(f"Клиент инициализирован: {me.username}")

    copier = ChannelCopier(client)

    print("=" * 50)
    print("ВЫБЕРИТЕ РЕЖИМ РАБОТЫ:")
    print("=" * 50)
    print("1 — Только старые посты (с удалением шаблонов)")
    print("2 — Пакетная отправка старых постов (с удалением шаблонов)")
    print("3 — РЕДАКТИРОВАНИЕ шаблонных постов (РАВНОМЕРНОЕ распределение) - НОВОЕ!")
    print("4 — РЕДАКТИРОВАНИЕ шаблонных постов (простая замена первых) - СТАРЫЙ МЕТОД")
    print("5 — УДАЛЕНИЕ конкретной картинки по media_id")
    print("6 — ВЫВОД всех media_id медиа в канале")
    print("=" * 50)

    mode = input("Введите номер режима: ").strip()

    if mode == "1":
        await copier.copy_old_messages()
    elif mode == "2":
        await copier.batch_copy_old_messages()
    elif mode == "3":
        await copier.copy_with_templates()  # НОВЫЙ метод с равномерным распределением
    elif mode == "4":
        await copier.copy_with_templates_simple()  # СТАРЫЙ метод (для обратной совместимости)
    elif mode == "5":
        target_media_id = int(input("Введите media_id картинки для удаления: ").strip())
        await copier.delete_media_by_id(target_media_id)
    elif mode == "6":
        await copier.list_all_media_ids()
    else:
        logger.error("Неверный режим работы!")

    await client.disconnect()
    logger.info("Работа завершена.")


if __name__ == "__main__":
    asyncio.run(main())
