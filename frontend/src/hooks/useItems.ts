import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { itemsApi } from '@/lib/api';
import {
  ItemDetail,
  ItemListResponse,
  ItemSearchResponse,
  ItemTemplateUpdate,
  PaletteCategoriesResponse,
  PropertyTypesResponse,
  PropertySubtypesResponse,
  PropertyCostValuesResponse,
} from '@/types/item';

export function useItemList(params: { offset?: number; limit?: number; base_item?: number }) {
  return useQuery<ItemListResponse>({
    queryKey: ['items', 'list', params],
    queryFn: () => itemsApi.list(params) as Promise<ItemListResponse>,
  });
}

export function useItemSearch(query: string, enabled = true) {
  return useQuery<ItemSearchResponse>({
    queryKey: ['items', 'search', query],
    queryFn: () => itemsApi.search(query) as Promise<ItemSearchResponse>,
    enabled: enabled && query.length > 0,
  });
}

export function useItem(resref: string | null) {
  return useQuery<ItemDetail>({
    queryKey: ['items', 'detail', resref],
    queryFn: () => itemsApi.get(resref!) as Promise<ItemDetail>,
    enabled: !!resref,
  });
}

export function useBaseItemCounts() {
  return useQuery({
    queryKey: ['items', 'base-items'],
    queryFn: () => itemsApi.baseItems(),
  });
}

export function useItemReferences(resref: string | null) {
  return useQuery({
    queryKey: ['items', 'references', resref],
    queryFn: () => itemsApi.getReferences(resref!),
    enabled: !!resref,
  });
}

export function useUpdateItemInstances() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (resref: string) => itemsApi.updateInstances(resref),
    onSuccess: () => {
      // Invalidate all relevant queries after bulk update
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['creatures'] });
      queryClient.invalidateQueries({ queryKey: ['areas'] });
    },
  });
}

export function useUpdateItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resref, data }: { resref: string; data: ItemTemplateUpdate }) =>
      itemsApi.update(resref, data as unknown as Record<string, unknown>) as Promise<ItemDetail>,
    onSuccess: (_, { resref, data }) => {
      const finalResref = data.new_resref || resref;
      // Invalidate item lists and the specific item detail
      queryClient.invalidateQueries({ queryKey: ['items', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['items', 'search'] });
      queryClient.invalidateQueries({ queryKey: ['items', 'detail', finalResref] });
      // If resref changed, also invalidate the old one
      if (data.new_resref && data.new_resref !== resref) {
        queryClient.invalidateQueries({ queryKey: ['items', 'detail', resref] });
        queryClient.invalidateQueries({ queryKey: ['items', 'references', resref] });
      }
    },
  });
}

export function usePaletteCategories() {
  return useQuery<PaletteCategoriesResponse>({
    queryKey: ['items', 'palette-categories'],
    queryFn: () => itemsApi.getPaletteCategories() as Promise<PaletteCategoriesResponse>,
    staleTime: Infinity,
  });
}

export function usePropertyTypes() {
  return useQuery<PropertyTypesResponse>({
    queryKey: ['items', 'property-types'],
    queryFn: () => itemsApi.getPropertyTypes() as Promise<PropertyTypesResponse>,
    staleTime: Infinity, // 2DA data never changes at runtime
  });
}

export function usePropertySubtypes(propertyId: number | null) {
  return useQuery<PropertySubtypesResponse>({
    queryKey: ['items', 'property-subtypes', propertyId],
    queryFn: () => itemsApi.getPropertySubtypes(propertyId!) as Promise<PropertySubtypesResponse>,
    enabled: propertyId !== null,
    staleTime: Infinity,
    retry: false, // Don't retry 404s (property has no subtypes)
  });
}

export function usePropertyCostValues(propertyId: number | null) {
  return useQuery<PropertyCostValuesResponse>({
    queryKey: ['items', 'property-cost-values', propertyId],
    queryFn: () => itemsApi.getPropertyCostValues(propertyId!) as Promise<PropertyCostValuesResponse>,
    enabled: propertyId !== null,
    staleTime: Infinity,
    retry: false, // Don't retry 404s (property has no cost values)
  });
}
