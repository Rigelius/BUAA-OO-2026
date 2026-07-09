import com.oocourse.library2.LibraryBookId;

import java.util.ArrayList;
import java.util.HashMap;

public class ReadingRoom {
    private final HashMap<LibraryBookId, Book> books = new HashMap<>();

    public void acceptReadBook(Book book) {
        books.put(book.getBookCopyId(), book);
    }

    public Book restoreBook(LibraryBookId bookId) {
        return books.remove(bookId);
    }

    public ArrayList<Book> drainBooks() {
        ArrayList<Book> result = new ArrayList<>(books.values());
        books.clear();
        return result;
    }
}
