import java.util.HashMap;

public final class FuncReg {
    // 函数定义注册表
    private final HashMap<String, FuncDef> definitions = new HashMap<>();

    public void put(FuncDef definition) {
        definitions.put(definition.getName(), definition);
    }

    public FuncDef get(String functionName) {
        return definitions.get(functionName);
    }

    // 函数定义实体
    public static final class FuncDef {
        private final String name;
        private final Expr bodyExpr;

        public FuncDef(String name, Expr bodyExpr) {
            this.name = name;
            this.bodyExpr = bodyExpr;
        }

        public String getName() {
            return name;
        }

        public Expr getBodyExpr() {
            return bodyExpr;
        }
    }
}