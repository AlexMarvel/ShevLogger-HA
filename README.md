# ShevLogger for Home Assistant

[![HACS validation](https://github.com/AlexMarvel/ShevLogger-HA/actions/workflows/validate.yml/badge.svg)](https://github.com/AlexMarvel/ShevLogger-HA/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/AlexMarvel/ShevLogger-HA)](https://github.com/AlexMarvel/ShevLogger-HA/releases/latest)

Офіційна локальна інтеграція шлюзу **ShevLogger** з Home Assistant. Вона
підключається до шлюзу напряму через домашню мережу, показує сенсори інвертора
та дозволяє змінювати доступні параметри.

Хмара SmartShev, MQTT і статична IP-адреса для роботи не потрібні.

## Можливості

- автоматичний пошук ShevLogger через mDNS;
- ручне підключення за IP-адресою або ім'ям хоста;
- локальна авторизація приватним LAN-токеном;
- сенсори, лічильники енергії та статистика Home Assistant;
- керування параметрами, які доступні у вибраному профілі інвертора;
- автоматичне оновлення набору сутностей після зміни профілю;
- українська та англійська мови.

## Встановлення через HACS

[![Відкрити репозиторій у HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=AlexMarvel&repository=ShevLogger-HA&category=integration)

1. Додайте `https://github.com/AlexMarvel/ShevLogger-HA` до **HACS →
   Інтеграції → Користувацькі репозиторії** як інтеграцію.
2. Встановіть **ShevLogger** і перезапустіть Home Assistant.
3. У SmartShev відкрийте **Шлюз → Фічі → Інтеграції → Home Assistant** та
   скопіюйте LAN-токен.
4. Відкрийте **Налаштування → Пристрої та служби** у Home Assistant і виберіть
   знайдений ShevLogger.

Якщо автоматичний пошук недоступний, додайте інтеграцію вручну та введіть
локальну адресу шлюзу і LAN-токен.

## Ручне встановлення

Скопіюйте `custom_components/shevlogger` до
`/config/custom_components/shevlogger` і перезапустіть Home Assistant.

## Як це працює

Home Assistant отримує всі поточні значення одним локальним запитом до шлюзу
кожні три секунди. Кількість сенсорів не збільшує кількість запитів. Дані та
керування залишаються доступними у локальній мережі без з'єднання з хмарою.

## Вимоги

- Home Assistant 2024.8 або новіший;
- ShevLogger з актуальною прошивкою;
- Home Assistant і шлюз у доступній локальній мережі;
- LAN-токен зі SmartShev.

[SmartShev](https://smartshev.pp.ua) · [Повідомити про проблему](https://github.com/AlexMarvel/ShevLogger-HA/issues)
