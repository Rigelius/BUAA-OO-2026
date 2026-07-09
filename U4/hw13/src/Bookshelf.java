import com.oocourse.library1.LibraryBookId;
import com.oocourse.library1.LibraryBookIsbn;
import com.oocourse.library1.LibraryTrace;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

public class Bookshelf {
    private final HashMap<LibraryBookIsbn, ArrayList<Book>> books = new HashMap<>();
    private final HashMap<LibraryBookId, Book> bookRecords = new HashMap<>();

    public Bookshelf(Map<LibraryBookIsbn, Integer> bookList) {
        for (Map.Entry<LibraryBookIsbn, Integer> entry : bookList.entrySet()) {
            LibraryBookIsbn isbn = entry.getKey();
            books.put(isbn, new ArrayList<>());
            for (int i = 1; i <= entry.getValue(); i++) {
                String copyId = String.format("%02d", i);
                LibraryBookId bookId = new LibraryBookId(isbn.getType(), isbn.getUid(), copyId);
                Book book = new Book(bookId);
                books.get(isbn).add(book);
                bookRecords.put(bookId, book);
            }
        }
    }

    public Book takeBook(LibraryBookIsbn isbn) {
        return books.get(isbn).remove(0);
    }

    public void putBook(Book book) {
        books.get(book.getIsbn()).add(book);
    }

    public boolean hasBook(LibraryBookIsbn isbn) {
        return !books.get(isbn).isEmpty();
    }

    public ArrayList<LibraryTrace> query(LibraryBookId bookCopyId) {
        return bookRecords.get(bookCopyId).queryMovingTrace();
    }
}
