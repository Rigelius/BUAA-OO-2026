import com.oocourse.library2.LibraryCloseCmd;
import com.oocourse.library2.LibraryCommand;
import com.oocourse.library2.LibraryIO;
import com.oocourse.library2.LibraryOpenCmd;
import com.oocourse.library2.LibraryReqCmd;
import com.oocourse.library2.LibraryBookIsbn;

import java.util.Map;

public class MainClass {
    public static void main(String[] args) {
        Map<LibraryBookIsbn, Integer> bookList = LibraryIO.SCANNER.getInventory();
        LibraryManager library = new LibraryManager(bookList);

        while (true) {
            LibraryCommand command = LibraryIO.SCANNER.nextCommand();
            if (command == null) {
                break;
            } else if (command instanceof LibraryOpenCmd) {
                library.open(command.getDate());
            } else if (command instanceof LibraryCloseCmd) {
                library.close(command.getDate());
            } else {
                library.serve((LibraryReqCmd) command);
            }
        }
    }
}
