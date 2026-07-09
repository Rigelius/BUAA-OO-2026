import com.oocourse.library2.LibraryBookIsbn;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;

public class TreasuredBookshelf {
    private final HashMap<LibraryBookIsbn, ArrayList<Book>> books = new HashMap<>();

    public TreasuredBookshelf(Map<LibraryBookIsbn, Integer> bookList) {
        for (LibraryBookIsbn isbn : bookList.keySet()) {
            books.put(isbn, new ArrayList<>());
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

    public ArrayList<Book> removeNormalBooks(HashSet<LibraryBookIsbn> treasuredIsbns) {
        ArrayList<Book> movedBooks = new ArrayList<>();
        for (LibraryBookIsbn isbn : books.keySet()) {
            if (treasuredIsbns.contains(isbn)) {
                continue;
            }
            ArrayList<Book> treasuredList = books.get(isbn);
            movedBooks.addAll(treasuredList);
            treasuredList.clear();
        }
        return movedBooks;
    }
}
