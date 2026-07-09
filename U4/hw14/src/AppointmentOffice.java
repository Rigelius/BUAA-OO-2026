import com.oocourse.library2.LibraryBookIsbn;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

public class AppointmentOffice {
    private final HashMap<String, LibraryBookIsbn> pendingOrders = new LinkedHashMap<>();
    private final HashMap<String, Book> keptBooks = new HashMap<>();
    private final HashMap<Book, LocalDate> keepDates = new HashMap<>();

    public void orderBook(String userId, LibraryBookIsbn isbn) {
        pendingOrders.put(userId, isbn);
    }

    public boolean hasOrdered(String userId) {
        return pendingOrders.containsKey(userId) || keptBooks.containsKey(userId);
    }

    public HashMap<String, LibraryBookIsbn> getPendingOrders() {
        return pendingOrders;
    }

    public void keepBook(String userId, Book book, LocalDate date, boolean beforeOpen) {
        keptBooks.put(userId, book);
        keepDates.put(book, beforeOpen ? date.plusDays(4) : date.plusDays(5));
    }

    public boolean hasReservedBook(String userId, LibraryBookIsbn isbn) {
        return keptBooks.containsKey(userId) && keptBooks.get(userId).getIsbn().equals(isbn);
    }

    public Book pickBook(String userId, LibraryBookIsbn isbn) {
        if (!hasReservedBook(userId, isbn)) {
            return null;
        }
        Book book = keptBooks.remove(userId);
        keepDates.remove(book);
        return book;
    }

    public HashMap<String, Book> query() {
        return new HashMap<>(keptBooks);
    }

    public HashMap<String, Book> getExpiredBooks(LocalDate date, boolean beforeOpen) {
        HashMap<String, Book> result = new HashMap<>();
        Iterator<Map.Entry<String, Book>> iterator = keptBooks.entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<String, Book> entry = iterator.next();
            LocalDate expireCloseDate = keepDates.get(entry.getValue());
            boolean expired = beforeOpen
                    ? date.isAfter(expireCloseDate)
                    : !date.isBefore(expireCloseDate);
            if (expired) {
                result.put(entry.getKey(), entry.getValue());
                keepDates.remove(entry.getValue());
                iterator.remove();
            }
        }
        return result;
    }
}
