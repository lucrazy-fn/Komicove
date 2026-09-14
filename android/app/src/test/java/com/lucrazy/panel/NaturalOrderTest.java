package com.lucrazy.panel;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.*;

public class NaturalOrderTest {
    @Test public void numericPagesSortNaturally(){List<String> pages=new ArrayList<>(Arrays.asList("page10.png","page2.png","page1.png"));pages.sort(new NaturalOrder());assertEquals(Arrays.asList("page1.png","page2.png","page10.png"),pages);}
    @Test public void hugeNumbersDoNotOverflow(){assertTrue(new NaturalOrder().compare("page999999999999999999999.png","page1000000000000000000000.png")<0);}
    @Test public void sameNumericPrefixContinuesComparing(){assertTrue(new NaturalOrder().compare("001a.png","1b.png")<0);}
}
