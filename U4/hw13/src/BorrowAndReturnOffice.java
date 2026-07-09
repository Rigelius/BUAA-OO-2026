import java.util.ArrayList;

public class BorrowAndReturnOffice {
    private final ArrayList<Book> books = new ArrayList<>();

    public void acceptReturnedBook(Book book) {
        books.add(book);
    }

    public ArrayList<Book> drainBooks() {
        ArrayList<Book> result = new ArrayList<>(books);
        books.clear();
        return result;
    }

    public ArrayList<Book> query() {
        return new ArrayList<>(books);
    }
}
