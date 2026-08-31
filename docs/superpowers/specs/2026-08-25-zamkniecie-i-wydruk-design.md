# Zamknięcie grafiku i wydruk PDF

**Data:** 25 sierpnia 2026 · **Stan:** zatwierdzone do wykonania

## Po co

Grafik da się ułożyć, ale nie da się go wynieść z aplikacji. Brakuje dwóch rzeczy:
momentu, w którym mówimy „gotowe", i kartki, którą można powiesić na tablicy.

## Zamknięcie

Przycisk **Zakończ grafik** w pasku siatki. Uruchamia sprawdzenie i otwiera okno
z wynikiem. Trzy wyjścia: *Zamknij i zapisz PDF*, *Tylko zamknij*, *Anuluj*.

Zamknięcie ustawia `status = FINAL` i `finalized_at`. Obie kolumny są w bazie od
pierwszej migracji i dotąd nikt ich nie wypełniał — nie ma migracji do dopisania.

Grafik zamknięty **nadal się edytuje**. Pierwsza zmiana — komórka, otwarcie albo
zamknięcie dnia — cofa go do `DRAFT` i pokazuje pod siatką jedno zdanie. Dzięki temu
`FINAL` znaczy „ktoś to przejrzał", a nie „ktoś to kiedyś przejrzał", i wywieszona
kartka nie rozjeżdża się z bazą po cichu.

Strzałka wstecz zostaje wyjściem bez ceremonii: komórki zapisują się na bieżąco.

## Sprawdzenie

Czysta funkcja nad `ScheduleData` i siatką zmian, bez bazy. Cztery rodzaje znalezisk:

| Rodzaj | Zatrzymuje | Znaczy |
|---|---|---|
| `EMPTY_DAY` | **tak** | apteka otwarta, nikogo nie wpisano |
| `NO_PHARMACIST` | nie | dziura w obsadzie magistra (istniejąca reguła) |
| `OUTSIDE_HOURS` | nie | zmiana wychodzi poza godziny otwarcia |
| `IDLE_PERSON` | nie | ktoś jest w składzie i nie ma ani jednego dnia |

Zatrzymuje tylko pierwszy: żeby przejść dalej, trzeba kliknąć „Zamknij mimo to".
Reszta jest wypisana jako uwagi. Wszystko to widać wyłącznie na ekranie.

## PDF

Jeden plik, strony w kolejności:

1. **Kierownik** — siatka dni × osoby, wiersz sum, braki obsady pod tabelą.
2. **Tablica** — ta sama siatka bez sum, większa czcionka.
3. **Po jednej stronie na osobę** — kalendarz miesiąca, godziny w kratkach, suma na dole.

Siatka idzie pionowo do siedmiu osób, powyżej poziomo; kartki osób zawsze pionowo
(mieszanie orientacji w jednym pliku sprawdzone, działa). Kolejność osób jak kolumny
w siatce. Nazwa pliku podpowiadana jako `Grafik-<nazwa>-<okres>.pdf`.

Drukowanie to ten sam rysunek na `QPrinter` zamiast do pliku — systemowe okno wyboru
drukarki, bez własnego podglądu.

Eksport dostępny **tylko dla grafiku gotowego**. Przy roboczym pozycje menu są
wyszarzone z podpowiedzią, co zrobić.

Na wydruku nie ma nazwy apteki, bo w bazie nie ma takiego pola. Tytułem jest nazwa
grafiku. Dodanie nazwy apteki to osobna tabela i migracja — poza zakresem.

## Gdzie się to klika

- Siatka: przycisk **Zakończ grafik**.
- Lista, menu kontekstowe: **Zapisz PDF…**, **Drukuj…**, **Wróć do roboczego**.

Przycisk w pasku łamie zasadę „bez przycisków akcji na paskach" z 0.2.0. Dokładany
na wyraźną prośbę właściciela; reszta zostaje w menu kontekstowym.

## Kod

```
services/audit.py        Finding, Audit, audit() — jedno miejsce, które wie, co jest nie tak
services/report.py       ScheduleReport — komplet danych do wydruku, zero ORM
export/paint.py          arkusz: czcionki, kolory, nagłówek, stopka, tekst wpasowany w kratkę
export/pages.py          trzy rodzaje stron
export/document.py       kolejność stron, orientacja, zapis do pliku albo na drukarkę
ui/schedules/finalize_dialog.py   okno zamknięcia
```

`export/` nie dotyka bazy: dostaje `ScheduleReport` i rysuje. Testy wydruku nie
potrzebują bazy, a zmiana wyglądu nie może zepsuć zapisu.

## Pułapki Qt zapisane z góry

**Punkty czcionki liczą się od rozdzielczości urządzenia.** Przy skalowaniu malarza
do jednostek punktowych rozmiar mnoży się dwa razy i tytuł wychodzi na pół strony.
`Sheet` skaluje malarza i dzieli rozmiary czcionek — na zewnątrz widać zwykłe punkty.

**`QFontMetricsF` bez urządzenia mierzy w 96 dpi**, więc dopasowanie tekstu do kratki
liczone bez `p.device()` daje złą szerokość i tekst i tak ucieka.

**Półpauza z Inter wychodzi w PDF jako znak z obszaru prywatnego** (``), więc
testy czytające tekst z PDF-a nie mogą porównywać myślników.

## Testy

Sprawdzenie: osobny test na każdy rodzaj znaleziska plus na to, że tylko `EMPTY_DAY`
zatrzymuje. Wydruk: liczba stron przy N osobach, każda strona pozioma, pełny miesiąc
z dziewięcioma osobami na jednej kartce, obecność nazwisk i sum w tekście PDF-a, brak
sum na stronie do tablicy, brak zawodu na kartce osoby, jeden rząd nazw dni przy
przełomie miesiąca, kolory tła próbkowane z pikseli. Interfejs: cofnięcie do roboczego
po edycji, wyszarzone pozycje menu przy roboczym.

## Czego nie robimy

Podglądu wydruku, wyboru zakresu stron, nazwy apteki, eksportu do innych formatów,
zapamiętywania ostatniego katalogu.
