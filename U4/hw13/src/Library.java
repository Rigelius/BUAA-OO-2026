import com.oocourse.library1.LibraryBookIsbn;
import com.oocourse.library1.LibraryBookState;
import com.oocourse.library1.LibraryIO;
import com.oocourse.library1.LibraryMoveInfo;
import com.oocourse.library1.LibraryReqCmd;
import com.oocourse.library1.LibraryTrace;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

public class Library {
    private final Bookshelf bookshelf;
    private final BorrowAndReturnOffice borrowAndReturnOffice;
    private final AppointmentOffice appointmentOffice;
    private final HashMap<String, Reader> users = new HashMap<>();

    public Library(Map<LibraryBookIsbn, Integer> bookList) {
        this.bookshelf = new Bookshelf(bookList);
        this.borrowAndReturnOffice = new BorrowAndReturnOffice();
        this.appointmentOffice = new AppointmentOffice();
    }

    public void open(LocalDate date) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        moves.addAll(arrangeExpiredAppointmentBooks(date, true));
        moves.addAll(arrange(date));
        moves.addAll(arrangePendingOrders(date, true));
        LibraryIO.PRINTER.move(date, moves);
    }

    public void close(LocalDate date) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        moves.addAll(arrangeExpiredAppointmentBooks(date, false));
        moves.addAll(arrange(date));
        moves.addAll(arrangePendingOrders(date, false));
        LibraryIO.PRINTER.move(date, moves);
    }

    public void serve(LibraryReqCmd cmd) {
        switch (cmd.getType()) {
            case QUERIED:
                query(cmd);
                break;
            case BORROWED:
                borrowBook(cmd);
                break;
            case RETURNED:
                returnBook(cmd);
                break;
            case ORDERED:
                orderBook(cmd);
                break;
            case PICKED:
                pickBook(cmd);
                break;
            default:
                break;
        }
    }

    public void borrowBook(LibraryReqCmd cmd) {
        LibraryBookIsbn isbn = cmd.getBookIsbn();
        Reader reader = getReader(cmd.getStudentId());
        if (reader.canHold(isbn) && bookshelf.hasBook(isbn)) {
            Book book = bookshelf.takeBook(isbn);
            move(book, LibraryBookState.USER, cmd.getDate());
            reader.borrow(book);
            LibraryIO.PRINTER.accept(cmd, book.getBookCopyId());
        } else {
            LibraryIO.PRINTER.reject(cmd);
        }
    }

    public void returnBook(LibraryReqCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        Book book = reader.returnBook(cmd.getBookId());
        if (book == null) {
            LibraryIO.PRINTER.reject(cmd);
            return;
        }
        move(book, LibraryBookState.BORROW_RETURN_OFFICE, cmd.getDate());
        borrowAndReturnOffice.acceptReturnedBook(book);
        LibraryIO.PRINTER.accept(cmd);
    }

    public void orderBook(LibraryReqCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        LibraryBookIsbn isbn = cmd.getBookIsbn();
        if (reader.canHold(isbn) && !appointmentOffice.hasOrdered(cmd.getStudentId())) {
            appointmentOffice.orderBook(cmd.getStudentId(), isbn);
            LibraryIO.PRINTER.accept(cmd);
        } else {
            LibraryIO.PRINTER.reject(cmd);
        }
    }

    public void pickBook(LibraryReqCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        LibraryBookIsbn isbn = cmd.getBookIsbn();
        if (reader.canHold(isbn) && appointmentOffice.hasReservedBook(cmd.getStudentId(), isbn)) {
            Book book = appointmentOffice.pickBook(cmd.getStudentId(), isbn);
            move(book, LibraryBookState.USER, cmd.getDate());
            reader.borrow(book);
            LibraryIO.PRINTER.accept(cmd, book.getBookCopyId());
        } else {
            LibraryIO.PRINTER.reject(cmd);
        }
    }

    public void query(LibraryReqCmd cmd) {
        ArrayList<LibraryTrace> traces = bookshelf.query(cmd.getBookId());
        LibraryIO.PRINTER.info(cmd.getDate(), cmd.getBookId(), traces);
    }

    public ArrayList<LibraryMoveInfo> arrange(LocalDate date) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        for (Book book : borrowAndReturnOffice.drainBooks()) {
            LibraryBookState from = book.getState();
            move(book, LibraryBookState.BOOKSHELF, date);
            bookshelf.putBook(book);
            moves.add(new LibraryMoveInfo(book.getBookCopyId(), from, LibraryBookState.BOOKSHELF));
        }
        return moves;
    }

    public ArrayList<LibraryMoveInfo> arrangeExpiredAppointmentBooks(
            LocalDate date, boolean beforeOpen) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        HashMap<String, Book> expiredBooks = appointmentOffice.getExpiredBooks(date, beforeOpen);
        for (Book book : expiredBooks.values()) {
            LibraryBookState from = book.getState();
            move(book, LibraryBookState.BOOKSHELF, date);
            bookshelf.putBook(book);
            moves.add(new LibraryMoveInfo(book.getBookCopyId(), from, LibraryBookState.BOOKSHELF));
        }
        return moves;
    }

    public ArrayList<LibraryMoveInfo> arrangePendingOrders(LocalDate date, boolean beforeOpen) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        Iterator<Map.Entry<String, LibraryBookIsbn>> iterator =
                appointmentOffice.getPendingOrders().entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<String, LibraryBookIsbn> entry = iterator.next();
            if (!bookshelf.hasBook(entry.getValue())) {
                continue;
            }
            Book book = bookshelf.takeBook(entry.getValue());
            LibraryBookState from = book.getState();
            move(book, LibraryBookState.APPOINTMENT_OFFICE, date);
            appointmentOffice.keepBook(entry.getKey(), book, date, beforeOpen);
            moves.add(new LibraryMoveInfo(
                    book.getBookCopyId(), from, LibraryBookState.APPOINTMENT_OFFICE,
                    entry.getKey()));
            iterator.remove();
        }
        return moves;
    }

    public void move(Book book, LibraryBookState to, LocalDate date) {
        book.moveTo(to, date);
    }

    private Reader getReader(String userId) {
        return users.computeIfAbsent(userId, Reader::new);
    }

}
